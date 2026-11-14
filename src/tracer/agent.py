"""The assistant on the shop floor. The model reads; code decides.

An operator asks why the checkweigher is rejecting bottles. Code works out what is being asked, which tools that
needs and whether this person may use them; the tools answer from the data and the knowledge graph; the answer is
assembled from what the tools returned, with the sources quoted. A language model may reword that answer (llm.py),
and its wording is dropped when it adds a number, a machine or a source the tools did not return.

There is no tool that writes to a machine. Opening a maintenance ticket is the only effect, and only a maintenance
lead may ask for it. Text in documents and tickets is data: it is ranked and quoted, never followed.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from . import graph
from .search import Index
from .store import Store
from .trace import STATES, Trace, trace

TICKET = re.compile(
    r"\b(open|create|raise|file|log)\b.*\bticket\b|\bticket\b.*\b(anlegen|aufmachen|eroeffnen|erstellen)\b"
)
CONTROL = re.compile(
    r"\b(stop|halt|shut ?down|restart|reset|start|set|change|increase|decrease|raise|lower)\b.*\b(line|speed|setpoint|machine|"
    r"temperature|torque|pressure)\b|\b(anhalten|stoppen|abschalten|neustarten|sollwert)\b"
)
CAUSE_WORDS = {
    "nozzle_clog": "a clogged filling nozzle",
    "torque_drift": "capper torque drifting low (worn clutch)",
    "glue_cold": "labeler glue too cold (heater)",
    "gripper_leak": "a vacuum leak at the palletizer gripper",
    "conveyor_jam": "a jam on the conveyor before the checkweigher",
    "loadcell_drift": "load cell drift on the checkweigher",
}


@dataclass
class Answer:
    text: str
    role: str
    intent: str
    tools: list[dict] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    refused: str | None = None
    trace: dict | None = None
    ticket: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def hhmm(ts: float) -> str:
    return datetime.fromtimestamp(ts, UTC).strftime("%H:%M")


class Agent:
    def __init__(self, store: Store, index: Index, cfg: dict, trace_cfg: dict, causes: list[list]):
        self.store = store
        self.index = index
        self.cfg = cfg
        self.trace_cfg = trace_cfg
        self.causes = causes
        self.glossary = index.glossary

    # ------------------------------------------------------------------------------------------ tools

    def allowed(self, role: str) -> set[str]:
        return set(self.cfg["roles"].get(role, []))

    def get_line_state(self, as_of: float) -> dict:
        out = {}
        for a in self.store.flow():
            s = self.store.state_at(a, as_of, as_of)
            out[a] = STATES.get(s, "no state signal") if s is not None else "no state signal"
        alarms = self.store.alarms(as_of - 1800, as_of, as_of)
        return {"states": out, "alarms": [{"code": c, "asset": a, "at": hhmm(t), "text": x} for c, a, t, x in alarms]}

    def trace_root_cause(self, asset: str, as_of: float) -> Trace:
        alarms = [a for a in self.store.alarms(as_of - 3600, as_of, as_of) if a[1] == asset]
        report = alarms[0][2] if alarms else as_of
        return trace(self.store, asset, report, as_of, self.trace_cfg, self.causes)

    def search_knowledge(self, query: str, k: int | None = None) -> list:
        return self.index.search(query, "hybrid", k)

    def get_signal(self, signal: str, minutes: int, as_of: float) -> dict:
        ts, v = self.store.series(signal, as_of - minutes * 60, as_of + 1, as_of)
        if not len(v):
            return {"signal": signal, "readings": 0}
        return {
            "signal": signal,
            "readings": int(len(v)),
            "last": round(float(v[-1]), 3),
            "min": round(float(v.min()), 3),
            "max": round(float(v.max()), 3),
        }

    def open_ticket(self, asset: str, summary: str, requested_by: str, as_of: float) -> int:
        cur = self.store.db.execute(
            "INSERT INTO opened_tickets (asset, summary, requested_by, ts) VALUES (?, ?, ?, ?)",
            (asset, summary, requested_by, as_of),
        )
        self.store.db.commit()
        return int(cur.lastrowid)

    # ------------------------------------------------------------------------------------------ the plan

    def symptom(self, question: str, as_of: float) -> str | None:
        ents = graph.entities(self.store, question, self.glossary)
        codes = [e for e, how in ents.items() if "-" in e]
        if codes:
            return codes[0].split("-")[0]
        ids = [e for e, how in ents.items() if how == "id"]
        if ids:
            return ids[0]
        named = [e for e in ents if "-" not in e]
        if named:
            return named[0]
        alarms = self.store.alarms(as_of - 3600, as_of, as_of)
        return alarms[-1][1] if alarms else None

    def ask(self, question: str, role: str, as_of: float | None = None) -> Answer:
        as_of = time.time() if as_of is None else as_of
        q = graph.fold(question)
        if role not in self.cfg["roles"]:
            return Answer("Unknown role; ask your shift lead for access.", role, "none", refused="unknown role")
        if CONTROL.search(q) and not TICKET.search(q):
            return Answer(
                "I cannot change machines or the line: no tool here writes to a PLC. Ask the shift lead to do it at "
                "the machine.",
                role,
                "control",
                refused="no tool writes to machines",
            )
        wants_ticket = bool(TICKET.search(q))
        if wants_ticket and "open_ticket" not in self.allowed(role):
            return Answer(
                "Only a maintenance lead can open a ticket from here. I can trace the fault for you; ask your "
                "maintenance lead to open the ticket.",
                role,
                "ticket",
                refused="open_ticket needs the maintenance_lead role",
            )
        a = Answer("", role, "ticket" if wants_ticket else "diagnose")
        asset = self.symptom(question, as_of)
        if asset is None:
            hits = self.search_knowledge(question)
            a.tools.append({"tool": "search_knowledge", "query": question})
            a.intent = "search"
            a.sources = [h.id for h in hits[: self.cfg["cite"]]]
            a.text = "No machine is alarming right now. Closest documents: " + ", ".join(
                f"{h.id} ({h.title})" for h in hits[: self.cfg["cite"]]
            )
            return a
        t = self.trace_root_cause(asset, as_of)
        a.tools.append({"tool": "trace_root_cause", "asset": asset})
        a.trace = t.to_dict()
        a.text, query, focus = self._explain(t)
        hits = self.search_knowledge(query, 10)
        a.tools.append({"tool": "search_knowledge", "query": query})
        about = {r[0] for r in self.store.q("SELECT doc FROM mentions WHERE entity = ?", focus)} if focus else set()
        cited = [h for h in hits if h.id in about][: self.cfg["cite"]] or hits[: self.cfg["cite"]]
        a.sources = [h.id for h in cited]
        if cited:
            a.text += " Sources: " + ", ".join(f"{h.id} ({h.title})" for h in cited) + "."
        if wants_ticket and t.root:
            summary = f"{t.root}: {CAUSE_WORDS.get(t.cause, 'unknown cause')}; first sign {t.signal} {t.direction} at {hhmm(t.onset_ts)}"
            a.ticket = self.open_ticket(t.root, summary, role, as_of)
            a.tools.append({"tool": "open_ticket", "asset": t.root})
            a.text += f" Opened ticket #{a.ticket} for {t.root}."
        return a

    def _explain(self, t: Trace) -> tuple[str, str, str | None]:
        if t.verdict == "insufficient_data":
            gone = ", ".join(t.silent)
            return (
                f"I cannot trace this: no data from {gone} in the last minutes. Check the network to {gone}.",
                f"{t.symptom} {gone} no data",
                t.symptom,
            )
        if t.verdict == "no_fault_found":
            where = {"upstream": "before", "downstream": "after", "here": "at"}[t.search]
            return (
                f"No machine {where} {t.symptom} shows readings out of their normal band in the last "
                f"{self.trace_cfg['scan_from_min']} minutes. This looks local to {t.symptom}.",
                t.symptom,
                t.symptom,
            )
        mins = round((t.report_ts - t.onset_ts) / 60)
        lead = f"{t.signal} on {t.root} went {t.direction} at {hhmm(t.onset_ts)}, {mins} min before the alarm on {t.symptom}"
        if t.root == t.symptom:
            head = f"The fault is at {t.root} itself: {lead}."
        else:
            head = f"The fault started at {t.root}, {'upstream' if t.search == 'upstream' else 'downstream'} of {t.symptom}: {lead}."
        if t.cause:
            text = f"{head} Likely cause: {CAUSE_WORDS.get(t.cause, t.cause)}. Suggested action: {t.action}."
            return text, f"{t.root} {CAUSE_WORDS.get(t.cause, t.cause)} {t.action}", t.root
        return (
            f"{head} The cause catalog has no entry for this signal; check {t.root} first.",
            f"{t.root} {t.signal.split('.')[-1].replace('_', ' ')}",
            t.root,
        )
