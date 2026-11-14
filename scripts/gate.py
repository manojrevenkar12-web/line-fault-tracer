"""The tracer against config/gate.toml on the dev report. Exit 1 on any failure."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def failures(r: dict, g: dict) -> list[str]:
    t, i, s, a = r["trace"], r["ingest"], r["search"]["hybrid"], r["agent"]
    out = []
    if t["tracer"]["right"] < g["min_root_and_cause"]:
        out.append(f"root and cause right {t['tracer']['right']}")
    if t["tracer"]["right"] - t["first_alarm"]["right"] < g["min_over_first_alarm"]:
        out.append(f"only {t['tracer']['right'] - t['first_alarm']['right']} more than the first alarm")
    if t["controls"]["tracer_false_alarms"] > g["max_false_alarms"]:
        out.append(f"false alarms {t['controls']['tracer_false_alarms']}")
    if i["clock_max_error_s"] > g["max_clock_error_s"]:
        out.append(f"clock error {i['clock_max_error_s']} s")
    if i["values"]["clean"]["share"] < g["min_clean_value_share"]:
        out.append(f"clean readings matching the truth {i['values']['clean']['share']}")
    if s["hit_at_5"] < g["min_hybrid_hit_at_5"]:
        out.append(f"search hit at 5 {s['hit_at_5']}")
    if a["right_and_cited"] < g["min_assistant_right_and_cited"]:
        out.append(f"assistant right and cited {a['right_and_cited']}")
    if a["permission_violations"] > g["max_permission_violations"]:
        out.append(f"permission violations {a['permission_violations']}")
    if a["injection"]["followed"] > g["max_injections_followed"]:
        out.append(f"injections followed {a['injection']['followed']}")
    return out


def main() -> None:
    r = json.loads((ROOT / "reports" / "dev.json").read_text())
    g = tomllib.loads((ROOT / "config" / "gate.toml").read_text())
    f = failures(r, g)
    for x in f:
        print("FAIL", x)
    print("Gate passed." if not f else "Gate failed.")
    sys.exit(1 if f else 0)


if __name__ == "__main__":
    main()
