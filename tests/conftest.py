import copy

import pytest

from tracer.core import Tracer
from tracer.settings import load
from tracer.world.sim import World


@pytest.fixture(scope="session")
def line():
    return load("line")


@pytest.fixture(scope="session")
def cfg():
    return load("tracer")


@pytest.fixture(scope="session")
def small(line):
    """A day of the dev line with four incidents: fast enough for every test run."""
    wc = copy.deepcopy(load("world"))
    wc.update(days=1, incidents=4, controls=3)
    wc["pipes"]["outages"] = 2
    wc["pipes"]["backlog_flushes"] = 1
    w = World(wc, line)
    return w, w.messages(), w.knowledge()


@pytest.fixture(scope="session")
def tracer(small, cfg, line):
    w, streams, knowledge = small
    t = Tracer(cfg=cfg, line=line)
    t.add_tag_export(knowledge["tag_export"])
    t.add_knowledge(knowledge)
    t.counts = t.ingest(streams)
    return t
