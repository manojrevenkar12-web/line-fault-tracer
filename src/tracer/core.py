"""The tracer as one object: the line, the knowledge graph, the clean data, the search index and the assistant."""

from __future__ import annotations

from pathlib import Path

from . import graph
from .agent import Agent
from .ingest import ingest
from .search import Index
from .settings import load
from .store import Store
from .trace import Trace, trace


class Tracer:
    def __init__(self, db: str | Path = ":memory:", cfg: dict | None = None, line: dict | None = None):
        self.cfg = cfg or load("tracer")
        self.line = line or load("line")
        self.store = Store(db)
        graph.load_line(self.store, self.line)
        self.index: Index | None = None
        self.agent: Agent | None = None
        if self.store.one("SELECT count(*) FROM documents"):
            self._index()

    def add_tag_export(self, export: list[dict]) -> int:
        graph.load_aliases(self.store, export, self.cfg["ingest"].get("approved_aliases", []))
        return int(self.store.one("SELECT count(*) FROM aliases"))

    def add_knowledge(self, knowledge: dict) -> dict[str, int]:
        out = graph.load_knowledge(self.store, knowledge, self.cfg["search"]["glossary"])
        self._index()
        return out

    def _index(self) -> None:
        self.index = Index(self.store, self.cfg["search"])
        self.agent = Agent(self.store, self.index, self.cfg["agent"], self.cfg["trace"], self.cfg["trace"]["causes"])

    def ingest(self, streams: dict[str, list[dict]], clean: bool = True) -> dict[str, int]:
        return ingest(self.store, streams, self.cfg["ingest"], self.line["units"], clean=clean)

    def trace(self, asset: str, report_ts: float, as_of: float) -> Trace:
        return trace(self.store, asset, report_ts, as_of, self.cfg["trace"], self.cfg["trace"]["causes"])
