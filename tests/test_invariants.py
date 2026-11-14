"""Nothing that serves reads the truth; settings live in config."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_only_the_evaluation_and_tests_import_the_world():
    for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        if "world" in p.parts or p.name in ("evaluate.py", "export.py"):
            continue
        assert not re.search(r"tracer\.world|from \.world|from \.\.world", p.read_text()), p


def test_the_world_config_is_read_only_by_the_evaluation():
    for p in (ROOT / "src").rglob("*.py"):
        if "world" in p.parts:
            continue
        assert 'load("world")' not in p.read_text() and 'load("heldout")' not in p.read_text(), p


def test_the_tracer_has_no_numbers_of_its_own_for_thresholds():
    src = (ROOT / "src" / "tracer" / "trace.py").read_text()
    for name in ("z_threshold", "consecutive", "smooth", "tie_s", "baseline_min", "scan_from_min"):
        assert f'cfg["{name}"]' in src


def test_no_tool_writes_to_a_machine(cfg):
    tools = {t for ts in cfg["agent"]["roles"].values() for t in ts}
    assert tools == {"get_line_state", "trace_root_cause", "search_knowledge", "get_signal", "open_ticket"}
    assert "open_ticket" not in cfg["agent"]["roles"]["operator"]
