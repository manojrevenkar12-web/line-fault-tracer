"""HTTP for the console and for the plant's other systems. The caller's role comes from the X-Role header, which the
plant's gateway sets after sign-in; the assistant checks it before every tool."""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from .core import Tracer


class Streams(BaseModel):
    opcua: list[dict] = []
    mqtt: list[dict] = []
    heartbeat: list[dict] = []
    alarm: list[dict] = []


class Question(BaseModel):
    question: str
    as_of: float | None = None


def create_app(tracer: Tracer | None = None) -> FastAPI:
    t = tracer or Tracer()
    app = FastAPI(title="line-fault-tracer", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {
            "ok": True,
            "samples": t.store.one("SELECT count(*) FROM samples"),
            "documents": t.store.one("SELECT count(*) FROM documents"),
        }

    @app.post("/tag-export")
    def tag_export(rows: list[dict]) -> dict:
        return {"aliases": t.add_tag_export(rows)}

    @app.post("/knowledge")
    def knowledge(body: dict) -> dict:
        return t.add_knowledge(body)

    @app.post("/ingest")
    def ingest(body: Streams) -> dict:
        return t.ingest(body.model_dump())

    @app.get("/quarantine")
    def quarantine() -> list[dict]:
        rows = t.store.q("SELECT tag, messages, suggestion FROM quarantine ORDER BY tag")
        return [{"tag": a, "messages": n, "suggestion": s} for a, n, s in rows]

    @app.get("/trace")
    def trace(asset: str, at: float, as_of: float | None = None) -> dict:
        if asset not in t.store.flow():
            raise HTTPException(404, f"no machine {asset!r} on this line")
        return t.trace(asset, at, as_of if as_of is not None else at).to_dict()

    @app.get("/search")
    def search(q: str, method: str = "hybrid") -> list[dict]:
        if t.index is None:
            raise HTTPException(409, "no knowledge loaded yet")
        try:
            hits = t.index.search(q, method)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return [{"id": h.id, "kind": h.kind, "title": h.title, "score": h.score} for h in hits]

    @app.post("/ask")
    def ask(body: Question, x_role: str = Header(...)) -> dict:
        if t.agent is None:
            raise HTTPException(409, "no knowledge loaded yet")
        return t.agent.ask(body.question, x_role, body.as_of).to_dict()

    return app
