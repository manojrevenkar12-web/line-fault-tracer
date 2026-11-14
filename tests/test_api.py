from fastapi.testclient import TestClient

from tracer.api import create_app
from tracer.core import Tracer


def test_the_api_end_to_end(small, cfg, line):
    w, streams, knowledge = small
    c = TestClient(create_app(Tracer(cfg=cfg, line=line)))
    assert c.post("/ask", json={"question": "x"}, headers={"X-Role": "operator"}).status_code == 409
    assert c.post("/tag-export", json=knowledge["tag_export"]).json()["aliases"] >= 18
    assert c.post("/knowledge", json=knowledge).json()["superseded_sections"] == 1
    r = c.post("/ingest", json=streams).json()
    assert r["samples"] > 0 and r["duplicates"] > 0
    assert c.get("/health").json()["ok"]
    inc = next(i for i in w.incidents if i.kind == "gripper_leak")
    t = c.get("/trace", params={"asset": inc.symptom_asset, "at": inc.report_ts, "as_of": inc.report_ts + 60}).json()
    assert (t["root"], t["cause"]) == ("R6", "gripper_leak")
    assert c.get("/trace", params={"asset": "X9", "at": 0}).status_code == 404
    assert c.get("/search", params={"q": "W4-A22"}).json()[0]["id"] == "M-W4-label"
    assert c.get("/search", params={"q": "x", "method": "magic"}).status_code == 400
    a = c.post(
        "/ask", json={"question": inc.report_text, "as_of": inc.report_ts + 60}, headers={"X-Role": "operator"}
    ).json()
    assert a["trace"]["root"] == "R6"
    assert c.post("/ask", json={"question": "why"}).status_code == 422
    assert c.get("/quarantine").json() == []
