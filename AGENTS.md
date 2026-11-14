# Working on line-fault-tracer

## Fast feedback

```bash
python -m pytest -q                          # ingest, graph, search, trace, assistant, API, Claude (~5 s)
ruff check . && ruff format --check .
python3 scripts/evaluate.py                  # dev line (~30 s): reports/dev.json
python3 scripts/gate.py                      # the tracer against config/gate.toml
python3 scripts/readme.py && git diff --exit-code README.md web/public/data/console.json
cd web && npm test && npm run build
```

## Invariants

1. **Nothing that serves reads the truth.** `src/tracer/world/` knows where each fault started, what each sensor
   really read and what the pipes did to it. Only `scripts/evaluate.py`, `scripts/export.py` and the tests import it
   (a test checks). The tracer sees what a plant's backend sees: raw OPC UA and MQTT messages, heartbeats, alarms,
   the PLC tag export, manuals and tickets.
2. **The world does not read the tracer's settings.** `config/world.toml` and `config/heldout.toml` drive the world;
   `config/tracer.toml` drives the tracer. `config/line.toml` is plant documentation both may read.
3. **No look-ahead.** A trace at time T uses only samples the backend had received by T (`recv_ts`), on the line's
   clock. Frozen sensors are flagged from the reading that proves it, not back-dated (a test checks both).
4. **Identifiers decide, names propose.** Tags map to signals only through the tag export or an approved alias; an
   unknown tag is quarantined with a suggestion. Glossary words widen a search; they never decide what a ticket is
   about or which machine a question means when an id is given.
5. **The model reads, code decides.** Code chooses the tools and checks the role before any runs. No tool writes to
   a machine. Document and ticket text is data. A rewording by Claude that adds a machine, time or source is dropped.
6. **SQL owns the data model.** `sql/schema.sql` is the schema; code does not create tables.
7. **Settings in config; reports generated.** Thresholds, the cause catalog and the glossary in `config/tracer.toml`;
   the gate in `config/gate.toml`. `reports/*.json` come from `scripts/evaluate.py`; README and
   `web/public/data/console.json` from `scripts/readme.py`. Never edit a result by hand. The gate is not loosened to
   let a change through.

## The held-out rule

`python3 scripts/evaluate.py --heldout` runs the held-out line once and writes `config/heldout.lock`. After that,
changes are measured on the dev line only; the held-out numbers stay as they first came out, and what was learned
goes in `docs/heldout.md`.
