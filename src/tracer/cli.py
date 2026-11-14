"""Command line: load a plant's files into a database, then trace, search and ask.

python -m tracer load data/example --db line.db
python -m tracer trace --db line.db --asset W4 --at 1793534520
python -m tracer search --db line.db "Waage zeigt Uebergewicht"
python -m tracer ask --db line.db --role operator --at 1793534580 "Why is W4 rejecting bottles?"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import Tracer


def read_dir(d: Path) -> tuple[dict[str, list[dict]], list[dict], dict]:
    streams = {}
    for name in ("opcua", "mqtt", "heartbeat", "alarm"):
        p = d / f"{name}.jsonl"
        streams[name] = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
    return streams, json.loads((d / "tag_export.json").read_text()), json.loads((d / "knowledge.json").read_text())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="tracer")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("load")
    a.add_argument("dir", type=Path)
    a.add_argument("--db", required=True)
    a.add_argument("--raw", action="store_true", help="store messages as they came, without cleaning")
    a = sub.add_parser("trace")
    a.add_argument("--db", required=True)
    a.add_argument("--asset", required=True)
    a.add_argument("--at", type=float, required=True)
    a = sub.add_parser("search")
    a.add_argument("--db", required=True)
    a.add_argument("--method", default="hybrid")
    a.add_argument("query")
    a = sub.add_parser("ask")
    a.add_argument("--db", required=True)
    a.add_argument("--role", default="operator")
    a.add_argument("--at", type=float, required=True)
    a.add_argument("question")
    args = p.parse_args(argv)

    t = Tracer(args.db)
    if args.cmd == "load":
        streams, export, knowledge = read_dir(args.dir)
        t.add_tag_export(export)
        k = t.add_knowledge(knowledge)
        c = t.ingest(streams, clean=not args.raw)
        print(json.dumps({"knowledge": k, "ingest": c}, indent=2))
        q = t.store.q("SELECT tag, messages, suggestion FROM quarantine")
        for tag, n, s in q:
            print(f"quarantined {tag}: {n} messages; closest signal {s} (a person decides)")
    elif args.cmd == "trace":
        print(json.dumps(t.trace(args.asset, args.at, args.at + 60).to_dict(), indent=2))
    elif args.cmd == "search":
        for h in t.index.search(args.query, args.method):
            print(f"{h.score:8.4f}  {h.id:10s}  {h.title}: {h.text[:70]}")
    elif args.cmd == "ask":
        ans = t.agent.ask(args.question, args.role, args.at)
        print(ans.text)
        if ans.refused:
            print(f"(refused: {ans.refused})")
    return 0
