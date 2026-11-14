"""Raw OPC UA samples, MQTT messages, heartbeats and alarms in; clean samples on one clock out.

What it fixes, in this order:
  device clocks   each device's offset from the line's clock, from its heartbeats (median, so late ones do not move it)
  names           PLC tags and MQTT topics mapped to signals through the tag export; unknown tags are quarantined
                  with a suggestion, never guessed into the data
  duplicates      the same MQTT message twice, and the same sample resent under a new id
  bad readings    sentinel values, and readings outside the signal's plausible range
  units           a reading in another unit (labelled or not) is converted when the conversion lands it in range
  frozen sensors  the same non-zero reading many times in a row, flagged from the moment it is known
  gaps and late   pauses in a signal, and samples that arrived minutes late from a buffer flush

clean=False stores the messages as they came (no clock, validity or unit fixes); evaluate.py uses it to show what
the cleaning is worth.
"""

from __future__ import annotations

import difflib
from collections import Counter, defaultdict

import numpy as np

from .store import Store


def clock_offsets(heartbeats: list[dict], latency: float) -> dict[str, tuple[float, int]]:
    by: dict[str, list[float]] = defaultdict(list)
    for h in heartbeats:
        by[h["device"]].append(h["source_ts"] - h["recv_ts"])
    return {d: (float(np.median(v)) + latency, len(v)) for d, v in by.items()}


def suggest(tag: str, known: dict[str, str], signals: list[str]) -> str | None:
    """A proposal for a person: the signal whose name is closest to the tag, among signals no tag maps to yet."""
    free = [s for s in signals if s not in set(known.values())]
    words = tag.replace("/", " ").replace(".", " ").replace("=", " ").replace(";", " ").lower()
    best = difflib.get_close_matches(words, [s.lower().replace(".", " ").replace("_", " ") for s in free], 1, 0.0)
    if not best:
        return None
    return next(s for s in free if s.lower().replace(".", " ").replace("_", " ") == best[0])


def convert(
    value: float, unit: str | None, canonical: str, lo: float, hi: float, units: dict
) -> tuple[float | None, str]:
    """A reading on the signal's own unit, and how it got there."""
    if unit and unit != canonical:
        u = units.get(unit)
        if u and u["to"] == canonical:
            return value * u["scale"] + u["offset"], f"converted:{unit}"
        return None, "invalid:unit"
    if lo <= value <= hi:
        return value, "ok"
    for name, u in units.items():
        if u["to"] == canonical:
            v = value * u["scale"] + u["offset"]
            if lo <= v <= hi:
                return v, f"converted:{name}"
    return None, "invalid:range"


def ingest(store: Store, streams: dict[str, list[dict]], cfg: dict, units: dict, clean: bool = True) -> dict[str, int]:
    db = store.db
    alias = dict(store.q("SELECT tag, signal FROM aliases"))
    meta = store.signal_meta()
    counts: Counter = Counter()

    offsets = clock_offsets(streams.get("heartbeat", []), cfg["expected_latency_s"])
    applied = {d: o for d, (o, _) in offsets.items() if clean and abs(o) >= cfg["min_clock_offset_s"]}
    db.executemany(
        "INSERT OR REPLACE INTO device_clock VALUES (?, ?, ?, ?)",
        [(d, round(o, 3), n, int(d in applied)) for d, (o, n) in sorted(offsets.items())],
    )

    res = cfg["dedupe_resolution_s"]
    sentinels = set(cfg["sentinels"])
    best: dict[tuple[str, float], list] = {}
    unknown: dict[str, list] = {}

    def take(tag: str, ts: float, value: float, unit: str | None, recv: float) -> None:
        counts["messages"] += 1
        sig = alias.get(tag)
        if sig is None:
            u = unknown.setdefault(tag, [0, recv])
            u[0] += 1
            u[1] = min(u[1], recv)
            counts["quarantined"] += 1
            return
        asset = sig.split(".")[0]
        ts = ts - applied.get(asset, 0.0)
        canonical, lo, hi = meta[sig]
        if not clean:
            v, quality = value, "ok"
        elif value in sentinels:
            v, quality = None, "invalid:sentinel"
        else:
            v, quality = convert(value, unit, canonical, lo, hi, units)
        key = (sig, round(round(ts / res) * res, 3))
        have = best.get(key)
        if have is not None:
            counts["duplicates"] += 1
            have[2] = min(have[2], recv)
            return
        best[key] = [v, quality, recv]

    for m in streams.get("opcua", []):
        take(m["node"], m["source_ts"], m["value"], m.get("eu"), m["server_ts"])
    for m in streams.get("mqtt", []):
        # a QoS 1 redelivery repeats the message id, a gateway resend does not; both repeat (signal, time), which is
        # what decides, so the earliest arrival is kept whatever order they come in
        p = m["payload"]
        take(m["topic"], p["ts"], p["v"], p.get("u"), m["recv_ts"])

    known = dict(alias)
    db.executemany(
        "INSERT OR REPLACE INTO quarantine VALUES (?, ?, ?, ?)",
        [(t, n, first, suggest(t, known, sorted(meta))) for t, (n, first) in sorted(unknown.items())],
    )

    by_signal: dict[str, list] = defaultdict(list)
    for (sig, ts), (v, quality, recv) in best.items():
        by_signal[sig].append([ts, v, recv, quality])
    rows, gaps = [], []
    for sig, items in sorted(by_signal.items()):
        items.sort(key=lambda x: x[0])
        unit = meta[sig][0]
        if clean and unit != "state":
            run = 0
            for i, it in enumerate(items):
                prev = items[i - 1][1] if i else None
                run = run + 1 if (it[1] is not None and it[1] == prev and it[1] != 0) else 1
                if run >= cfg["stuck_samples"]:
                    it[3] = "stuck"
        ts = np.array([x[0] for x in items])
        if len(ts) > 2:
            step = float(np.median(np.diff(ts)))
            for a, b in zip(ts[:-1], ts[1:], strict=False):
                if b - a > cfg["gap_factor"] * step:
                    gaps.append((sig, float(a), float(b)))
        for t, v, recv, quality in items:
            counts[quality.split(":")[0]] += 1
            if recv - t > cfg["late_after_s"]:
                counts["late"] += 1
            rows.append((sig, t, v, recv, quality))
    db.executemany("INSERT OR REPLACE INTO samples VALUES (?, ?, ?, ?, ?)", rows)
    db.executemany("INSERT OR REPLACE INTO gaps VALUES (?, ?, ?)", gaps)
    counts["gaps"] = len(gaps)
    counts["samples"] = len(rows)

    alarm_rows = []
    for a in streams.get("alarm", []):
        asset = a["code"].split("-")[0]
        alarm_rows.append((a["code"], asset, a["source_ts"] - applied.get(asset, 0.0), a["recv_ts"], a["text"]))
    db.executemany("INSERT OR REPLACE INTO alarms VALUES (?, ?, ?, ?, ?)", alarm_rows)
    counts["alarms"] = len(alarm_rows)
    db.executemany("INSERT OR REPLACE INTO ingest_counts VALUES (?, ?)", sorted(counts.items()))
    db.commit()
    return dict(sorted(counts.items()))
