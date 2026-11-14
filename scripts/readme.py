"""Write README.md and the console data from reports/*.json. Never edit the results by hand."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/manojrevenkar12-web/line-fault-tracer"
KINDS = {
    "nozzle_clog": "Clogged filling nozzle (F1)",
    "torque_drift": "Capper torque drift (C2)",
    "glue_cold": "Cold labeler glue (L3)",
    "gripper_leak": "Palletizer vacuum leak (R6)",
    "conveyor_jam": "Conveyor jam (CV34)",
    "loadcell_drift": "Checkweigher load cell drift (W4)",
    "pressure_surge": "Fill pressure surge (F1), not in the cause catalog",
}


def table(head: list[str], rows: list[list[str]], left: int = 1) -> str:
    sep = "|" + "|".join(["---"] * left + ["--:"] * (len(head) - left)) + "|"
    return "\n".join(["| " + " | ".join(head) + " |", sep] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def trace_table(t: dict) -> str:
    n = t["incidents"]
    rows = [
        ["**Right machine and right cause**"]
        + [f"**{t[k]['right']} of {n}**" for k in ("first_alarm", "raw", "tracer")],
        ["Right machine"] + [f"{t[k]['right_root']} of {n}" for k in ("first_alarm", "raw", "tracer")],
        [
            f"Says something is wrong where nothing was ({t['controls']['n']} operator reports of a short stop)",
            "n/a",
            str(t["controls"]["raw_false_alarms"]),
            str(t["controls"]["tracer_false_alarms"]),
        ],
    ]
    return table(["", "Go to the alarming machine", "Tracer on raw data", "Tracer"], rows)


def kinds_table(t: dict) -> str:
    by: dict[str, list] = {}
    for x in t["rows"]:
        by.setdefault(x["kind"], []).append(x)
    rows = []
    for k, xs in by.items():
        rows.append(
            [
                KINDS.get(k, k),
                xs[0]["symptom"]
                if len({x["symptom"] for x in xs}) == 1
                else "/".join(sorted({x["symptom"] for x in xs})),
                len(xs),
                sum(x["first_alarm"]["right"] for x in xs),
                sum(x["raw"]["right"] for x in xs),
                sum(x["tracer"]["right"] for x in xs),
            ]
        )
    return table(["Fault", "Where it alarms", "Incidents", "Alarming machine", "Raw data", "Tracer"], rows)


def ingest_table(i: dict) -> str:
    clock = ", ".join(f"{d} {v['true_s']:+.0f} s (found {v['estimated_s']:+.2f})" for d, v in i["clock"].items())
    rows = [
        ["Messages (OPC UA samples and MQTT)", f"{i['messages']:,}", ""],
        [
            "Duplicates and resends",
            f"{i['duplicates']['injected']:,} sent twice",
            f"{i['duplicates']['removed']:,} removed",
        ],
        ["Device clocks off", clock, f"largest error {i['clock_max_error_s']} s"],
        ["Failed reads (-9999)", f"{i['sentinels']['injected']:,}", f"{i['sentinels']['caught']:,} caught"],
        ["Readings in another unit after a firmware update, unit label missing", "", f"{i['converted']:,} converted"],
        ["Connection drops", str(i["outages"]["injected"]), f"{i['outages']['found']} found as gaps"],
        [
            "Samples from buffer flushes, minutes late",
            f"{i['late']['injected']:,}",
            f"{i['late']['flagged']:,} flagged late",
        ],
        ["Frozen sensor", "1 sensor", f"{i['stuck_flagged']:,} readings flagged"],
        [
            "**Stored readings that match what the sensor measured, at the right time**",
            f"raw: {i['values']['raw']['share'] * 100:.1f}%",
            f"**clean: {i['values']['clean']['share'] * 100:.2f}%**",
        ],
    ]
    if i["quarantine"]:
        q = i["quarantine"][0]
        rows.append(
            [
                "Tags the PLC export does not list",
                f"{len(i['quarantine'])} ({q['tag']})",
                f"quarantined, suggestion {q['suggestion']} ({'right' if q['suggestion_right'] else 'wrong'})",
            ]
        )
    return table(["What the pipes did", "Put in by the simulator", "What ingest did"], rows)


def search_table(s: dict) -> str:
    names = {
        "identifiers": "Identifiers only (graph)",
        "words": "Words (BM25 + glossary)",
        "spelling": "Spelling (char n-grams)",
        "hybrid": "**Hybrid (used)**",
    }
    rows = [
        [
            names[k],
            f"{v['hit_at_5']} of {v['of']}",
            f"{v['manual_at_5']} of {v['of']}",
            f"{v['mrr']:.3f}",
            f"{v['precision_at_5']:.3f}",
        ]
        for k, v in s.items()
        if k in names
    ]
    order = list(names)
    rows.sort(key=lambda r: order.index(next(k for k, n in names.items() if n == r[0])))
    return table(
        ["Ranking", "Relevant source in top 5", "Right manual section in top 5", "MRR", "Precision at 5"], rows
    )


def agent_table(a: dict) -> str:
    p = a["permissions"]
    rows = [
        [
            "Operator questions (half in German) answered with the right machine and cause",
            f"{a['right']} of {a['questions']}",
        ],
        ["... and quoting a relevant manual section or ticket", f"{a['right_and_cited']} of {a['questions']}"],
        ["Operators asking to open a ticket: refused", f"{p['operator_refused']} of {p['operator_asks']}"],
        [
            "Maintenance leads asking: ticket opened on the root machine, not the alarming one",
            f"{p['lead_opened_on_root']} of {p['lead_asks']}",
        ],
        [
            "Requests to stop, reset or change a machine: refused before any tool runs",
            f"{a['control']['refused_without_tools']} of {a['control']['asks']}",
        ],
        [
            "Planted ticket telling the assistant to stop the line: retrieved / followed",
            f"{a['injection']['retrieved']} / {a['injection']['followed']}",
        ],
        ["**Permission violations**", f"**{a['permission_violations']}**"],
    ]
    return table(["", "Dev line"], rows)


def heldout_section(h: dict | None) -> str:
    if h is None:
        return "## Held-out line\n\nNot run yet: `python3 scripts/evaluate.py --heldout` (once).\n"
    t, a, s = h["trace"], h["agent"], h["search"]["hybrid"]
    return f"""## Held-out line (run once)

A second plant from the same integrator: other OPC UA node ids and MQTT topics, three other device clocks off (one of
them the checkweigher, where most symptoms show), a capper that switches to reporting torque in Ncm, a palletizer
vacuum tag nobody has mapped, 30% weak faults, more duplicates and outages, and one kind of fault the cause catalog
has never seen. It ran once with the code and settings the dev line ended on (`config/heldout.lock`).

{trace_table(t)}

{kinds_table(t)}

Ingest: clock error {h["ingest"]["clock_max_error_s"]} s, {h["ingest"]["values"]["clean"]["share"] * 100:.2f}% of clean
readings match the truth (raw {h["ingest"]["values"]["raw"]["share"] * 100:.1f}%). Search: {s["hit_at_5"]} of {s["of"]} with a
relevant source in the top five. Assistant: {a["right_and_cited"]} of {a["questions"]} right and cited,
{a["permission_violations"]} permission violations, {a["injection"]["followed"]} injections followed.

The {t["controls"]["tracer_false_alarms"]} false alarms are the main finding: both reports came about an hour after an
earlier fault ended, while the end of that fault was still in the baseline window, so signals returning to normal
looked like new departures. What went wrong and what changed on the dev line afterwards (a recovery rule, tested on
the dev line): [docs/heldout.md](docs/heldout.md).
"""


def readme(r: dict, h: dict | None) -> str:
    t, i = r["trace"], r["ingest"]
    n = t["incidents"]
    return f"""# line-fault-tracer

When bottles get rejected at the checkweigher, the alarm sits at the checkweigher. On the simulated line, the fault
started at another machine in **{t["symptom_not_at_root"]} of {n}** incidents: a clogged nozzle on the filler, a worn
clutch on the capper, cold glue on the labeler. Going to the machine that alarms finds the right machine and cause
{t["first_alarm"]["right"]} times out of {n}.

This repository takes what a packaging line's backend really receives (OPC UA samples and MQTT messages with
duplicates, clocks that run off, a unit that changed with a firmware update, failed reads, connection drops and
late buffer flushes), cleans it onto one clock, links machines, signals, alarm codes, manual sections and past
maintenance tickets in a knowledge graph, traces a symptom back along the material flow to the machine where it
started, and gives operators an assistant that answers with sources and cannot change a machine.

All numbers below come from `scripts/evaluate.py` on a simulated seven-machine line ({r["line"]["days"]} days,
{r["line"]["signals"]} signals every {r["line"]["sample_s"]} s, {n} incidents, {t["controls"]["n"]} false reports). The
truth (where each fault started, what each sensor really read) lives only in `src/tracer/world/`; nothing that
serves imports it.

![Console](docs/console.png)

## Results on the dev line

### Root cause

{trace_table(t)}

{kinds_table(t)}

When it found the right machine, the tracer put the start of the fault within a median of
{t["onset_error_min_median"]} minutes of when it really began, using only data the backend had received by the time
the operator called. The worst ({t["onset_error_min_max"]} minutes) are weak load-cell drifts: a scale that creeps
4 g over 40 minutes is only distinguishable from noise once it has crept most of the way.

### Data pipes

{ingest_table(i)}

Raw data looks fine on a chart, but in it the capper's clock runs {i["clock"].get("C2", {}).get("true_s", 0):+.0f} s
off, so torque changes appear after the rejects they cause, and runs of -9999 look like faults. That is the difference
between the raw and the clean column in the root-cause table.

### Search over manuals and tickets

36 questions the way people on a line write them: alarm codes alone, German ("Etikettenleim zu kalt",
"Greifervakuum zu niedrig"), typos ("palletiser vaccum low"), symptoms without the machine's name. The manual for the
checkweigher exists in two versions that disagree; the superseded one is never returned.

{search_table(r["search"])}

### Assistant

{agent_table(r["agent"])}

{heldout_section(h)}
## How it works

| Step | Module | What it does |
|---|---|---|
| Ingest | `src/tracer/ingest.py` | Device clocks from heartbeats (median), tags to signals through the PLC tag export, unknown tags quarantined with a suggestion for a person, duplicates by (signal, time) keeping the earliest arrival, sentinels and out-of-range readings out, unlabelled units converted when the conversion lands in range, frozen sensors flagged from the moment they are known, gaps and late samples recorded. |
| Data model | `sql/schema.sql`, `src/tracer/store.py` | One SQLite file: assets, material flow, signals, aliases, clean samples with the time each one arrived, alarms, documents, mentions, tickets opened. |
| Knowledge graph | `src/tracer/graph.py` | Upstream and downstream by recursive SQL over the flow; documents linked to the assets and alarm codes they mention; manual versions linked to what replaced them. Identifiers decide; glossary words only propose. |
| Search | `src/tracer/search.py` | BM25 with a plant glossary, German compound splitting and stemming; character n-grams for typos; alarm codes and asset ids typed in the question as a boost; fused by reciprocal rank. |
| Trace | `src/tracer/trace.py` | Upstream for a quality problem or a starved machine, downstream for a blocked one. Robust z (median, MAD) of a short moving mean against the hour before; the earliest lasting departure is the root; a departure the cause catalog does not know is reported as unknown, not matched to the nearest story. |
| Assistant | `src/tracer/agent.py`, `src/tracer/llm.py` | Code picks the tools and checks the role; tools answer from the data; the answer quotes its sources. No tool writes to a PLC. Claude may reword the answer in the asker's language; a rewording with a machine, time or source the tools did not return is dropped. |
| API | `src/tracer/api.py` | FastAPI: `/ingest`, `/tag-export`, `/knowledge`, `/trace`, `/search`, `/ask` (role from the `X-Role` header), `/quarantine`. |

## Run it

```bash
pip install -e '.[dev]'
python -m pytest -q                       # 48 tests, about 6 s
python3 scripts/evaluate.py               # dev line, about 30 s: reports/dev.json
python3 scripts/gate.py                   # against config/gate.toml

python -m tracer load data/example --db /tmp/line.db
python -m tracer ask --db /tmp/line.db --role operator --at 1793535493 "Underweight rejects high on W4 (W4-A17), why?"
python -m tracer search --db /tmp/line.db "Greifervakuum zu niedrig"
uvicorn --factory tracer.api:create_app   # the HTTP API

cd web && npm ci && npm run dev           # the console
```

## What a real plant changes

- The tag export, the glossary and the cause catalog are the plant's: `config/tracer.toml` holds the dev line's, and
  a maintenance lead can read and change every row. A tag the export does not list stays in quarantine until a person
  maps it.
- The tracer needs the order of the line and a state signal on each machine. Lines that branch (two fillers into one
  labeler) need the flow as a graph, which `flow` in `sql/schema.sql` already is; the recursive queries follow it.
- A fault the catalog has never seen gets the right machine and "cause unknown"; the held-out line has one.
- Thresholds were set on the dev line and checked once on the held-out line; a real line gets a few weeks of
  shadow running against maintenance records before anyone acts on the answer.

Repository: {REPO}
"""


def console(r: dict, h: dict | None) -> dict:
    def slim(rep: dict) -> dict:
        t = rep["trace"]
        return {
            "world": rep["world"],
            "line": rep["line"],
            "settings": rep["settings"],
            "flow": rep["flow"],
            "assets": rep["assets"],
            "trace": {
                k: t[k]
                for k in (
                    "incidents",
                    "symptom_not_at_root",
                    "tracer",
                    "raw",
                    "first_alarm",
                    "onset_error_min_median",
                    "controls",
                )
            },
            "incidents": [
                {
                    k: x[k]
                    for k in (
                        "id",
                        "kind",
                        "known_kind",
                        "weak",
                        "symptom",
                        "root",
                        "search",
                        "true_onset_min",
                        "tracer",
                        "raw",
                        "first_alarm",
                        "lanes",
                    )
                }
                for x in t["rows"]
            ],
            "ingest": rep["ingest"],
            "search": rep["search"],
            "agent": {k: v for k, v in rep["agent"].items() if k != "rows"},
            "answers": {x["id"]: {k: x[k] for k in ("question", "answer", "sources")} for x in rep["agent"]["rows"]},
            "kinds": KINDS,
        }

    return {"dev": slim(r), "heldout": slim(h) if h else None}


def main() -> None:
    r = json.loads((ROOT / "reports" / "dev.json").read_text())
    hp = ROOT / "reports" / "heldout.json"
    h = json.loads(hp.read_text()) if hp.exists() else None
    (ROOT / "README.md").write_text(readme(r, h))
    out = ROOT / "web" / "public" / "data"
    out.mkdir(parents=True, exist_ok=True)
    (out / "console.json").write_text(json.dumps(console(r, h), separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
