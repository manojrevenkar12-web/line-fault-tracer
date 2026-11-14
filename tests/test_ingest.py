import random

from hypothesis import given, settings
from hypothesis import strategies as st

from tracer.core import Tracer
from tracer.ingest import clock_offsets, convert, suggest

UNITS = {
    "degF": {"to": "degC", "scale": 0.5555556, "offset": -17.7777778},
    "Ncm": {"to": "Nm", "scale": 0.01, "offset": 0.0},
}


def test_clock_offsets_are_found_from_heartbeats(small, tracer):
    w, _, _ = small
    est = dict(tracer.store.q("SELECT device, offset_s FROM device_clock"))
    for d, off in w.cfg["pipes"]["clock_offset_s"].items():
        assert abs(est[d] - off) < 0.5
    assert abs(est["F1"]) < 0.5


def test_every_duplicate_and_resend_is_removed_and_nothing_else(small, tracer):
    w, _, _ = small
    inj = w.pipe_truth()["injected"]
    assert tracer.counts["duplicates"] == inj["duplicates"] + inj["resends"]


def test_sentinels_never_reach_the_data(small, tracer):
    w, _, _ = small
    assert tracer.store.one("SELECT count(*) FROM samples WHERE value <= -9000") == 0
    assert (
        tracer.store.one("SELECT count(*) FROM samples WHERE quality = 'invalid:sentinel'")
        == w.pipe_truth()["injected"]["sentinels"]
    )


def test_glue_temperature_in_fahrenheit_is_converted(tracer):
    lo, hi = tracer.store.q(
        "SELECT min(value), max(value) FROM samples WHERE signal = 'L3.glue_temp' AND value IS NOT NULL"
    )[0]
    assert 80 <= lo and hi <= 220
    assert tracer.store.one("SELECT count(*) FROM samples WHERE quality = 'converted:degF'") > 0


def test_convert():
    assert round(convert(329.0, None, "degC", 80, 220, UNITS)[0], 1) == 165.0
    assert convert(329.0, None, "degC", 80, 220, UNITS)[1] == "converted:degF"
    assert convert(220.0, "Ncm", "Nm", 0, 6, UNITS) == (2.2, "converted:Ncm")
    assert convert(5000.0, None, "degC", 80, 220, UNITS) == (None, "invalid:range")
    assert convert(150.0, None, "degC", 80, 220, UNITS) == (150.0, "ok")
    assert convert(1.0, "furlong", "Nm", 0, 6, UNITS) == (None, "invalid:unit")


def test_offsets_ignore_late_heartbeats():
    hb = [{"device": "C2", "source_ts": t + 240, "recv_ts": t + 0.3} for t in range(100)]
    hb += [{"device": "C2", "source_ts": t + 240, "recv_ts": t + 900} for t in range(10)]
    assert abs(clock_offsets(hb, 0.3)["C2"][0] - 240) < 0.01


def test_an_unknown_tag_is_quarantined_with_a_suggestion_not_mapped(small, cfg, line):
    w, streams, knowledge = small
    c = dict(cfg)
    c["ingest"] = dict(cfg["ingest"], approved_aliases=[])
    t = Tracer(cfg=c, line=line)
    t.add_tag_export(knowledge["tag_export"])
    t.ingest(streams)
    q = t.store.q("SELECT tag, suggestion FROM quarantine")
    assert q == [("line1/robot6/vac", "R6.gripper_vacuum")]
    assert t.store.one("SELECT count(*) FROM samples WHERE signal = 'R6.gripper_vacuum'") == 0


def test_suggest_only_proposes_signals_nobody_maps_yet():
    known = {"a/r6/cycle": "R6.cycle_time"}
    assert suggest("line1/robot6/vac", known, ["R6.cycle_time", "R6.gripper_vacuum"]) == "R6.gripper_vacuum"


def _tiny(n: int, seed: int):
    rnd = random.Random(seed)
    out = {"opcua": [], "mqtt": [], "heartbeat": [], "alarm": []}
    for i in range(n):
        t = 1000.0 + 30 * i
        v = round(2.5 + rnd.random() * 0.1, 4)
        out["opcua"].append(
            {"node": "ns=2;s=Filler01.FillPressure", "source_ts": t, "server_ts": t + 0.2, "value": v, "eu": "bar"}
        )
        m = {"topic": "line1/cw4/weight", "msg_id": f"m{i}", "recv_ts": t + 0.3, "payload": {"ts": t, "v": 500 + i % 3}}
        out["mqtt"].append(m)
        if rnd.random() < 0.3:
            out["mqtt"].append(dict(m, recv_ts=t + 2))
        if rnd.random() < 0.2:
            out["opcua"].append(dict(out["opcua"][-1], server_ts=t + 9))
    return out


def _load(streams, cfg, line):
    t = Tracer(cfg=cfg, line=line)
    t.add_tag_export(
        [
            {"tag": "ns=2;s=Filler01.FillPressure", "signal": "F1.fill_pressure", "source": "x"},
            {"tag": "line1/cw4/weight", "signal": "W4.weight", "source": "x"},
        ]
    )
    t.ingest(streams)
    return t.store.q("SELECT * FROM samples ORDER BY signal, ts")


@settings(max_examples=25, deadline=None)
@given(st.integers(5, 40), st.integers(0, 10_000), st.randoms(use_true_random=False))
def test_arrival_order_does_not_change_the_data(n, seed, rnd):
    from tracer.settings import load

    cfg, line = load("tracer"), load("line")
    s = _tiny(n, seed)
    shuffled = {k: rnd.sample(v, len(v)) for k, v in s.items()}
    assert _load(s, cfg, line) == _load(shuffled, cfg, line)


def test_loading_the_same_batch_twice_changes_nothing(cfg, line):
    s = _tiny(30, 1)
    t = Tracer(cfg=cfg, line=line)
    t.add_tag_export([{"tag": "line1/cw4/weight", "signal": "W4.weight", "source": "x"}])
    t.ingest(s)
    before = t.store.q("SELECT * FROM samples ORDER BY signal, ts")
    t.ingest(s)
    assert t.store.q("SELECT * FROM samples ORDER BY signal, ts") == before


def test_a_frozen_sensor_is_flagged_only_once_it_is_known(cfg, line):
    s = {"opcua": [], "heartbeat": [], "alarm": [], "mqtt": []}
    for i in range(40):
        v = 501.234 if 5 <= i < 35 else 500 + i * 0.01
        s["mqtt"].append(
            {"topic": "line1/cw4/weight", "msg_id": f"m{i}", "recv_ts": 30 * i + 0.3, "payload": {"ts": 30 * i, "v": v}}
        )
    t = Tracer(cfg=cfg, line=line)
    t.add_tag_export([{"tag": "line1/cw4/weight", "signal": "W4.weight", "source": "x"}])
    t.ingest(s)
    q = [x for (x,) in t.store.q("SELECT quality FROM samples ORDER BY ts")]
    k = cfg["ingest"]["stuck_samples"]
    assert q[5 : 5 + k - 1] == ["ok"] * (k - 1) and q[5 + k - 1 : 35] == ["stuck"] * (35 - 5 - k + 1)


def test_outages_show_as_gaps(small, tracer):
    w, _, _ = small
    gaps = tracer.store.q("SELECT signal, start, stop FROM gaps")
    for dev, a, b in w.pipe_truth()["outages"]:
        assert any(s.startswith(dev + ".") and g0 <= b and g1 >= a for s, g0, g1 in gaps)


def test_an_approval_for_another_plant_does_not_block_the_suggestion(small, cfg, line):
    w, streams, knowledge = small
    c = dict(cfg)
    c["ingest"] = dict(
        cfg["ingest"], approved_aliases=[{"tag": "other/plant/vac", "signal": "R6.gripper_vacuum", "approved_by": "x"}]
    )
    t = Tracer(cfg=c, line=line)
    t.add_tag_export(knowledge["tag_export"])
    t.ingest(streams)
    assert t.store.q("SELECT tag, suggestion FROM quarantine") == [("line1/robot6/vac", "R6.gripper_vacuum")]


def test_duplicates_of_a_quarantined_tag_are_counted_as_duplicates(small, cfg, line):
    w, streams, knowledge = small
    c = dict(cfg)
    c["ingest"] = dict(cfg["ingest"], approved_aliases=[])
    t = Tracer(cfg=c, line=line)
    t.add_tag_export(knowledge["tag_export"])
    counts = t.ingest(streams)
    inj = w.pipe_truth()["injected"]
    assert counts["duplicates"] == inj["duplicates"] + inj["resends"]
