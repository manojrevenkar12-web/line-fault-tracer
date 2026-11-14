"""From a symptom to the machine where it started.

A checkweigher rejecting bottles, a packer that cannot get rid of its cases: the alarm sits where the symptom shows,
not where the fault is. The tracer follows the material flow from the symptom (upstream for a quality problem or a
starved machine, downstream for a blocked one), finds when each signal on each machine first left its normal band,
and calls the machine with the earliest departure the root. What that first departure means comes from a catalog a
maintenance lead can read and edit (config/tracer.toml); a departure the catalog does not know is reported as
"root found, cause unknown" rather than matched to the nearest story.

Only data the backend had received by `as_of` is used, on the line's clock.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from . import graph
from .store import Store

STATES = {0: "running", 1: "starved", 2: "blocked", 3: "fault", 4: "stopped"}


@dataclass
class Onset:
    asset: str
    signal: str
    ts: float
    direction: str
    z: float


@dataclass
class Trace:
    symptom: str
    report_ts: float
    as_of: float
    search: str
    verdict: str  # root_found, no_fault_found, insufficient_data
    root: str | None = None
    cause: str | None = None
    action: str | None = None
    signal: str | None = None
    direction: str | None = None
    onset_ts: float | None = None
    onsets: list[Onset] = field(default_factory=list)
    silent: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def first_departure(
    ts: np.ndarray, v: np.ndarray, base: np.ndarray, cfg: dict, state: bool
) -> tuple[float, str, float] | None:
    if len(base) < 5 or len(v) < cfg["consecutive"]:
        return None
    med = float(np.median(base))
    if state:
        hit = (v == cfg["fault_state"]) & (med != cfg["fault_state"])
        idx = np.flatnonzero(hit)
        return (float(ts[idx[0]]), "up", 99.0) if len(idx) else None
    mad = 1.4826 * float(np.median(np.abs(base - med)))
    if mad <= 0:
        mad = max(1e-6, float(np.std(base)))
    w = cfg["smooth"]
    if len(v) < w + cfg["consecutive"]:
        return None
    # mean of the last w readings, so a small lasting shift stands out of the noise; stamped at its last reading,
    # the moment the shift could be known
    mean = np.convolve(v, np.ones(w) / w, "valid")
    z = (mean - med) / (mad / np.sqrt(w))
    ts = ts[w - 1 :]
    out = np.abs(z) > cfg["z_threshold"]
    k = cfg["consecutive"]
    run = np.convolve(out.astype(int), np.ones(k, dtype=int), "valid")
    idx = np.flatnonzero(run == k)
    if not len(idx):
        return None
    i = int(idx[0])
    return float(ts[i]), "up" if z[i] > 0 else "down", round(float(z[i]), 1)


def direction_for(store: Store, asset: str, report_ts: float, as_of: float) -> str:
    state = store.state_at(asset, report_ts, as_of)
    if state == 2:
        return "downstream"
    if state == 3:
        return "here"
    return "upstream"


def onsets_for(store: Store, asset: str, report_ts: float, as_of: float, cfg: dict) -> list[Onset]:
    b0, b1 = cfg["baseline_min"]
    out = []
    for sig, unit in store.asset_signals(asset):
        _, base = store.series(sig, report_ts - b0 * 60, report_ts - b1 * 60, as_of)
        ts, v = store.series(sig, report_ts - cfg["scan_from_min"] * 60, as_of + 1, as_of)
        hit = first_departure(ts, v, base, cfg, unit == "state")
        if hit and unit != "state" and recovering(store, sig, base, v[ts >= hit[0]], report_ts, as_of, cfg):
            continue
        if hit:
            out.append(Onset(asset, sig, hit[0], hit[1], hit[2]))
    return out


def recovering(
    store: Store, sig: str, base: np.ndarray, after: np.ndarray, report_ts: float, as_of: float, cfg: dict
) -> bool:
    """The baseline window was itself off the signal's usual level (an earlier fault was still going on) and the
    departure moves back towards that level: the end of the earlier fault, not a new one."""
    _, usual = store.series(sig, report_ts - cfg["usual_hours"] * 3600, report_ts - cfg["baseline_min"][1] * 60, as_of)
    if len(usual) < 20 or not len(after):
        return False
    med = float(np.median(usual))
    mad = max(1.4826 * float(np.median(np.abs(usual - med))), 1e-6)
    off = abs(float(np.median(base)) - med)
    return off > cfg["z_threshold"] * mad and abs(float(np.median(after)) - med) < off


def trace(store: Store, symptom: str, report_ts: float, as_of: float, cfg: dict, causes: list[list]) -> Trace:
    search = direction_for(store, symptom, report_ts, as_of)
    if search == "downstream":
        candidates = [symptom, *graph.downstream(store, symptom)]
    elif search == "here":
        candidates = [symptom]
    else:
        candidates = [symptom, *graph.upstream(store, symptom)]
    found: list[Onset] = []
    silent = []
    for a in candidates:
        seen = store.last_seen(a, as_of)
        if seen is None or seen < as_of - 300:
            silent.append(a)
        found += onsets_for(store, a, report_ts, as_of, cfg)
    found.sort(key=lambda o: o.ts)
    if found:
        # departures within one tie window: the one farthest from the symptom is where it started, since a fault
        # travels along the line towards the symptom
        dist = {a: i for i, a in enumerate(candidates)}
        tied = [o for o in found if o.ts - found[0].ts <= cfg["tie_s"]]
        lead = max(tied, key=lambda o: (dist[o.asset], -o.ts))
        found.remove(lead)
        found.insert(0, lead)
    t = Trace(symptom, report_ts, as_of, search, "no_fault_found", onsets=found, silent=silent)
    if not found:
        t.verdict = "insufficient_data" if silent else "no_fault_found"
        return t
    first = found[0]
    t.verdict, t.root, t.onset_ts = "root_found", first.asset, first.ts
    catalog = {(a, s, d): (c, act) for a, s, d, c, act in causes}
    for o in (o for o in found if o.asset == first.asset):
        if (o.asset, o.signal, o.direction) in catalog:
            t.cause, t.action = catalog[(o.asset, o.signal, o.direction)]
            t.signal, t.direction = o.signal, o.direction
            break
    else:
        t.signal, t.direction = first.signal, first.direction
    return t


def first_alarm(store: Store, symptom: str, causes: list[list]) -> tuple[str, str | None]:
    """What happens without the tracer: maintenance goes to the machine that alarms and checks what can go wrong
    there."""
    here = [c for a, _, _, c, _ in causes if a == symptom]
    return symptom, (here[0] if here else None)
