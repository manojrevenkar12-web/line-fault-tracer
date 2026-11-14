"""The plant as a graph: machines in material-flow order, the signals on each, the names people and devices use for
them, and the documents that mention them. Identifiers (asset ids, alarm codes, PLC tags) decide what a text is about;
glossary words only propose."""

from __future__ import annotations

import re
import unicodedata

from .store import Store

ALARM = re.compile(r"\b([A-Z]{1,2}\d{1,2}-A\d{2})\b")


def fold(text: str) -> str:
    """Lower case, umlauts written out (ü -> ue), accents removed."""
    t = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()


def load_line(store: Store, line: dict) -> None:
    db = store.db
    order = {a: i for i, a in enumerate(line["flow"])}
    db.executemany(
        "INSERT OR REPLACE INTO assets VALUES (?, ?, ?, ?)",
        [(a["id"], a["type"], a["name"], order[a["id"]]) for a in line["assets"]],
    )
    db.executemany("INSERT OR REPLACE INTO flow VALUES (?, ?)", list(zip(line["flow"], line["flow"][1:], strict=False)))
    db.executemany(
        "INSERT OR REPLACE INTO signals VALUES (?, ?, ?, ?, ?)",
        [(s["id"], s["id"].split(".")[0], s["unit"], s["range"][0], s["range"][1]) for s in line["signals"]],
    )
    db.commit()


def load_aliases(store: Store, export: list[dict], approved: list[dict]) -> None:
    rows = [(e["tag"], e["signal"], e["source"]) for e in export]
    rows += [(a["tag"], a["signal"], f"approved: {a['approved_by']}") for a in approved]
    store.db.executemany("INSERT OR REPLACE INTO aliases VALUES (?, ?, ?)", rows)
    store.db.commit()


def upstream(store: Store, asset: str) -> list[str]:
    """Machines before `asset` in the material flow, nearest first."""
    rows = store.q(
        "WITH RECURSIVE up(id, d) AS (SELECT src, 1 FROM flow WHERE dst = ? "
        "UNION SELECT f.src, up.d + 1 FROM flow f JOIN up ON f.dst = up.id) SELECT id FROM up ORDER BY d",
        asset,
    )
    return [r[0] for r in rows]


def downstream(store: Store, asset: str) -> list[str]:
    rows = store.q(
        "WITH RECURSIVE down(id, d) AS (SELECT dst, 1 FROM flow WHERE src = ? "
        "UNION SELECT f.dst, down.d + 1 FROM flow f JOIN down ON f.src = down.id) SELECT id FROM down ORDER BY d",
        asset,
    )
    return [r[0] for r in rows]


def entities(store: Store, text: str, glossary: dict[str, str] | None = None) -> dict[str, str]:
    """Assets and alarm codes a text is about, each with how it was found: 'id' (an identifier) or 'glossary'."""
    assets = {r[0] for r in store.q("SELECT id FROM assets")}
    found: dict[str, str] = {}
    for code in ALARM.findall(text.upper()):
        found[code] = "id"
        asset = code.split("-")[0]
        if asset in assets:
            found.setdefault(asset, "id")
    for tok in re.findall(r"[A-Za-z]+\d+", text):
        if tok.upper() in assets:
            found[tok.upper()] = "id"
    if glossary:
        for word in re.findall(r"[a-z]+", fold(text)):
            for part in glossary.get(word, "").split():
                if part in assets:
                    found.setdefault(part, "glossary")
    return found


def load_knowledge(store: Store, knowledge: dict, glossary: dict[str, str]) -> dict[str, int]:
    db = store.db
    manuals = knowledge["manuals"]
    latest: dict[tuple, dict] = {}
    for m in manuals:
        key = (m["asset"], tuple(sorted(m["alarms"])))
        if key not in latest or m["version"] > latest[key]["version"]:
            latest[key] = m
    rows, mentions = [], []
    superseded = 0
    for m in manuals:
        newest = latest[(m["asset"], tuple(sorted(m["alarms"])))]
        sup = newest["id"] if newest["id"] != m["id"] else None
        superseded += sup is not None
        rows.append((m["id"], "manual", m["title"], m["text"], m["asset"], m["version"], None, sup, "vendor manual"))
        ents = {m["asset"], *m["alarms"], *entities(store, m["text"])}
        mentions += [(m["id"], e) for e in ents]
    for t in knowledge["tickets"]:
        title = t["text"] if len(t["text"]) <= 50 else t["text"][:48].rsplit(" ", 1)[0] + " ..."
        rows.append((t["id"], "ticket", title, t["text"], None, None, t["date"], None, "maintenance log"))
        mentions += [(t["id"], e) for e in entities(store, t["text"], glossary)]
    db.executemany("INSERT OR REPLACE INTO documents VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    db.executemany("INSERT OR REPLACE INTO mentions VALUES (?, ?)", mentions)
    db.commit()
    return {"documents": len(rows), "superseded_sections": superseded, "mentions": len(mentions)}
