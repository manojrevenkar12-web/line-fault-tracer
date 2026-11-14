# Repeatable tasks

## Connect a real line
1. Write `config/line.toml` for it: machines, the material flow, every signal with its unit and plausible range, the
   state codes and the unit conversions its devices use.
2. Export the PLC tag list in the shape of `data/example/tag_export.json` and post it to `/tag-export`.
3. Post manuals and maintenance tickets to `/knowledge` in the shape of `data/example/knowledge.json`.
4. Stream OPC UA samples, MQTT messages, heartbeats and alarms to `/ingest` in batches. Check `/quarantine` and have a
   maintenance lead approve mappings in `[[ingest.approved_aliases]]`.

## Teach the tracer a new cause
1. Add a row to `causes` in `config/tracer.toml`: asset, signal, direction, cause id, action.
2. Add the cause's words to `CAUSE_WORDS` in `src/tracer/agent.py` and to `KINDS` in `scripts/readme.py`.
3. To measure it, add the fault to `config/world.toml` (`[kinds.<id>]`) and run the fast feedback.

## Add plant vocabulary
1. Add the word and what it means to `[search.glossary]` in `config/tracer.toml` (folded: ü as ue).
2. Run `scripts/evaluate.py`: the search table shows whether it helped.

## Change a detection setting
1. `[trace]` in `config/tracer.toml`. Run `scripts/evaluate.py` and `scripts/gate.py`; false alarms on the controls
   and the onset error move together, so read both.
