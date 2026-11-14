"""Write a few hours of the dev line as the files a plant would hand over, for the command line and the console demo.

python scripts/export.py data/example        # the hours around the first incident
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tracer.settings import load  # noqa: E402
from tracer.world.sim import World  # noqa: E402

RECV = {"opcua": "server_ts", "mqtt": "recv_ts", "heartbeat": "recv_ts", "alarm": "recv_ts"}


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "data" / "example")
    out.mkdir(parents=True, exist_ok=True)
    w = World(load("world"), load("line"))
    inc = w.incidents[0]
    a, b = inc.report_ts - 2 * 3600, inc.report_ts + 120
    for name, msgs in w.messages().items():
        keep = [m for m in msgs if a <= m[RECV[name]] <= b]
        (out / f"{name}.jsonl").write_text("".join(json.dumps(m, separators=(",", ":")) + "\n" for m in keep))
    k = w.knowledge()
    (out / "tag_export.json").write_text(json.dumps(k["tag_export"], indent=1) + "\n")
    (out / "knowledge.json").write_text(json.dumps({"manuals": k["manuals"], "tickets": k["tickets"]}, indent=1) + "\n")
    (out / "README.md").write_text(
        f"Two hours of the dev line before the operator's report on {inc.symptom_asset} at epoch {inc.report_ts:.0f} "
        f"({inc.report_text!r}).\nWritten by scripts/export.py. Try:\n\n"
        f"    python -m tracer load data/example --db /tmp/line.db\n"
        f'    python -m tracer ask --db /tmp/line.db --role operator --at {inc.report_ts + 60:.0f} "{inc.report_text}"\n'
    )


if __name__ == "__main__":
    main()
