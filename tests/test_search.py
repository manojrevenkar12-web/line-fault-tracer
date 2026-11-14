from tracer.search import split_compound, stem, words


def test_german_compounds_split_into_plant_words(cfg):
    g = cfg["search"]["glossary"]
    assert split_compound("greifervakuum", g) == ["greifer", "vakuum"]
    assert stem("gripper") in words("Greifervakuum zu niedrig", g)


def test_stem():
    assert stem("untergewichtig") == "untergewicht" and stem("labels") == "label" and stem("cap") == "cap"


def test_the_superseded_manual_section_is_never_returned(tracer):
    assert tracer.store.one("SELECT superseded_by FROM documents WHERE id = 'M-W4-v1'") == "M-W4-v2"
    for q in ("W4-A17", "underweight rejects", "load cell"):
        assert "M-W4-v1" not in [h.id for h in tracer.index.search(q, "hybrid", 20)]


def test_alarm_code_finds_its_manual_section(tracer):
    assert tracer.index.search("W4-A21", "hybrid")[0].id == "M-W4-cap"


def test_typos_still_find_the_manual(tracer):
    assert "M-R6" in [h.id for h in tracer.index.search("palletiser vaccum low", "hybrid")]


def test_unknown_method(tracer):
    import pytest

    with pytest.raises(ValueError):
        tracer.index.search("x", "magic")
