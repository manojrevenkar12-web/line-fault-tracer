import httpx

from tracer.llm import Claude, grounded

ANSWER = (
    "The fault started at F1, upstream of W4: F1.fill_pressure on F1 went down at 03:12, 7 min before the alarm on W4. "
    "Sources: M-F1 (Filler: fill pressure), T012 (Ticket T012)."
)


def client(text: str) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"content": [{"type": "text", "text": text}]}))
    )


def test_a_grounded_rewording_is_kept():
    text = "Die Ursache liegt am F1 (Abfueller): der Fuelldruck fiel um 03:12, 7 min vor dem Alarm an W4. Quellen: M-F1, T012."
    assert Claude("m", 100, client(text), key="k").reword(ANSWER, "Warum?") == text


def test_a_rewording_that_names_another_machine_is_dropped():
    assert Claude("m", 100, client("The fault is at C2, check the capper."), key="k").reword(ANSWER, "why") == ANSWER


def test_a_rewording_with_a_new_time_is_dropped():
    assert Claude("m", 100, client("F1 went down at 03:40."), key="k").reword(ANSWER, "why") == ANSWER


def test_grounded():
    assert grounded("F1 at 03:12", ANSWER) and not grounded("R6 at 03:12", ANSWER) and not grounded("see T099", ANSWER)
