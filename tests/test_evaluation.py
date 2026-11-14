"""The committed dev report is what the gate reads, and it passes."""

import json
import tomllib
from pathlib import Path

from gate import failures

ROOT = Path(__file__).resolve().parents[1]


def test_the_committed_dev_report_passes_the_gate():
    r = json.loads((ROOT / "reports" / "dev.json").read_text())
    g = tomllib.loads((ROOT / "config" / "gate.toml").read_text())
    assert failures(r, g) == []


def test_the_gate_fails_a_worse_report():
    r = json.loads((ROOT / "reports" / "dev.json").read_text())
    g = tomllib.loads((ROOT / "config" / "gate.toml").read_text())
    r["agent"]["permission_violations"] = 1
    r["trace"]["tracer"]["right"] = 10
    assert len(failures(r, g)) >= 2


def test_the_report_counts_add_up():
    r = json.loads((ROOT / "reports" / "dev.json").read_text())
    t = r["trace"]
    assert len(t["rows"]) == t["incidents"] and len(t["control_rows"]) == t["controls"]["n"]
    assert r["ingest"]["duplicates"]["removed"] == r["ingest"]["duplicates"]["injected"]
