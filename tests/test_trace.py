import numpy as np

from tracer import graph
from tracer.trace import first_departure, trace

CFG = {"z_threshold": 6.0, "consecutive": 3, "smooth": 5, "fault_state": 3}


def test_the_line_graph(tracer):
    assert graph.upstream(tracer.store, "W4") == ["CV34", "L3", "C2", "F1"]
    assert graph.downstream(tracer.store, "P5") == ["R6"]


def test_noise_is_not_a_departure():
    rng = np.random.default_rng(1)
    ts = np.arange(200) * 30.0
    assert first_departure(ts, rng.normal(0, 1, 200), rng.normal(0, 1, 100), CFG, False) is None


def test_a_step_is_found_where_it_happens():
    rng = np.random.default_rng(2)
    ts = np.arange(100) * 30.0
    v = rng.normal(0, 1, 100)
    v[40:] += 5
    t, d, _ = first_departure(ts, v, rng.normal(0, 1, 100), CFG, False)
    assert d == "up" and 40 * 30 <= t <= 46 * 30


def test_a_machine_entering_fault_is_a_departure():
    ts = np.arange(20) * 30.0
    v = np.zeros(20)
    v[7:] = 3
    assert first_departure(ts, v, np.zeros(10), CFG, True)[0] == 7 * 30


def test_every_incident_on_the_small_line_is_traced_to_its_root(small, tracer):
    w, _, _ = small
    for inc in w.incidents:
        t = tracer.trace(inc.symptom_asset, inc.report_ts, inc.report_ts + 60)
        assert (t.root, t.cause) == (inc.root, inc.kind), inc


def test_nothing_is_found_where_nothing_was_wrong(small, tracer):
    w, _, _ = small
    for c in w.controls:
        assert tracer.trace(c["asset"], c["report_ts"], c["report_ts"] + 60).verdict == "no_fault_found"


def test_no_look_ahead(small, tracer):
    """A trace at time T gives the same answer whatever arrived after T."""
    w, _, _ = small
    inc = w.incidents[0]
    as_of = inc.report_ts + 60
    before = tracer.trace(inc.symptom_asset, inc.report_ts, as_of).to_dict()
    tracer.store.db.execute(
        "INSERT OR REPLACE INTO samples VALUES ('F1.fill_pressure', ?, 99.0, ?, 'ok')", (inc.report_ts - 600, as_of + 5)
    )
    assert tracer.trace(inc.symptom_asset, inc.report_ts, as_of).to_dict() == before
    tracer.store.db.rollback()


def test_a_cause_the_catalog_does_not_know_is_reported_as_unknown(small, tracer, cfg):
    w, _, _ = small
    inc = next(i for i in w.incidents if i.kind == "nozzle_clog")
    causes = [c for c in cfg["trace"]["causes"] if c[3] != "nozzle_clog"]
    t = trace(tracer.store, inc.symptom_asset, inc.report_ts, inc.report_ts + 60, cfg["trace"], causes)
    assert t.root == "F1" and t.cause is None and t.signal == "F1.fill_pressure"


def test_the_end_of_an_earlier_fault_is_not_a_new_one(small, tracer, cfg):
    """A report an hour after a fault ended: the baseline window still holds the fault, and its end looks like a
    departure unless it is recognised as a return to the usual level."""
    w, _, _ = small
    fooled = 0
    for inc in w.incidents:
        at = inc.end + 55 * 60
        assert tracer.trace(inc.symptom_asset, at, at + 60).verdict == "no_fault_found", inc
        off = dict(cfg["trace"], usual_hours=0)
        fooled += (
            trace(tracer.store, inc.symptom_asset, at, at + 60, off, cfg["trace"]["causes"]).verdict == "root_found"
        )
    assert fooled > 0
