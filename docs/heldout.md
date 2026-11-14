# Held-out line: what it showed

Run once on 2026-11-14 with the code and settings the dev line ended on (commit 4cdfac8). `reports/heldout.json` is
that run and is not regenerated; `config/heldout.lock` stops a second run. Everything below was fixed, if at all, on
the dev line and measured there.

## What held

- **Root cause: 24 of 24** right machine and right cause, against 3 for going to the alarming machine and 9 for the
  same tracer on raw data. 21 of 24 faults started at another machine than the one that alarmed.
- **The fault the catalog had never seen** (a fill pressure surge on F1, which makes the checkweigher reject
  overweight bottles): all 3 traced to F1 with "cause unknown", none matched to the nearest story. Going to the
  alarming machine sends maintenance to recalibrate the checkweigher's load cell, which the manual lists first for
  W4-A18.
- **Ingest** found three new device clocks (F1 -200 s, P5 +310 s, and the checkweigher +45 s) within 0.03 s, and
  converted the capper's switch to Ncm without being told about it. 99.99% of clean readings match what the sensor
  measured; raw, 49%.
- **The palletizer vacuum tag nobody had mapped** stayed in quarantine. The vacuum leak was still traced to R6, from
  the robot entering its fault state.
- **Assistant**: 24 of 24 right and quoting a relevant source; 0 permission violations; the planted instruction was
  retrieved and not followed.

## What went wrong

1. **2 false alarms on 10 reports where nothing was wrong** (dev: 0). Both reports came about an hour after an
   earlier fault ended (I19, cold glue, ended 61 min before; I12, conveyor jam, 66 min before). The baseline window
   (95 to 50 minutes before the report) still held the end of that fault, so the signals returning to normal looked
   like departures: glue temperature "up", motor current "down".
   *Fix on dev:* a departure is dropped when the baseline window was itself off the signal's usual level (median of
   the six hours before) and the departure moves back towards it (`recovering` in `src/tracer/trace.py`,
   `usual_hours` in `config/tracer.toml`). The dev controls never landed that close to an incident, so the dev
   report did not change; `test_the_end_of_an_earlier_fault_is_not_a_new_one` reproduces the situation on the dev
   line (a report 55 minutes after every incident ends) and fails without the rule.
2. **No suggestion for the quarantined tag.** The approval for the dev plant's palletizer vacuum tag in
   `config/tracer.toml` was loaded for the held-out plant too and counted as "R6.gripper_vacuum is taken", so the
   suggestion came back empty. *Fix on dev:* only tags that delivered data in this load count as taken
   (`test_an_approval_for_another_plant_does_not_block_the_suggestion`).
3. **Duplicates removed 15,876 of 16,752, failed reads caught 1,351 of 1,404.** Not data errors: the missing 876 and
   53 were on the quarantined tag, whose messages never reach the data. They were counted as quarantined, not as
   duplicates or failed reads. *Fix on dev:* quarantined messages are deduplicated and their failed reads counted
   (`test_duplicates_of_a_quarantined_tag_are_counted_as_duplicates`).
4. **Onset error up to 22 minutes** (median 3.8): weak load-cell drifts again, as on the dev line. Not changed; a
   scale creeping a few grams over 40 minutes is noise until it has crept most of the way.

## What a real line would add

The false alarms are the finding that matters: on a real line faults cluster, so "an hour after the last one" is
common. Before anyone acts on the tracer, a few weeks of shadow running against the maintenance log would show how
often a report lands near the end of an earlier fault, and whether six hours is the right memory for "usual".
