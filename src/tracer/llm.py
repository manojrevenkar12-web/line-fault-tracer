"""Optional: Claude rewords the assistant's answer for the person asking, in their language. The facts are code's.
A rewording that carries a number, a machine id, an alarm code or a source id the answer did not have is dropped and
the answer goes out as code wrote it.

Off by default; set ANTHROPIC_API_KEY to use it. Tested against a fake API (tests/test_llm.py).
"""

from __future__ import annotations

import os
import re

import httpx

API = "https://api.anthropic.com/v1/messages"
FACT = re.compile(r"\b[A-Z]{1,2}\d{1,2}-A\d{2}\b|\b(?:CV|[A-Z])\d{1,2}\b|\b[MT]-?[A-Z0-9-]*\d+\b|\d+(?:[.:]\d+)?")


def facts(text: str) -> set[str]:
    return set(FACT.findall(text))


def grounded(text: str, source: str) -> bool:
    return facts(text) <= facts(source)


class Claude:
    def __init__(self, model: str, max_tokens: int, client: httpx.Client | None = None, key: str | None = None):
        self.model = model
        self.max_tokens = max_tokens
        self.key = key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.http = client or httpx.Client(timeout=30)

    def reword(self, answer: str, question: str) -> str:
        r = self.http.post(
            API,
            json={
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": "You help operators on a bottling line. Reword the answer below for the person who asked, in "
                "the language of their question, in at most four short sentences. Keep every machine id, time and "
                "source id as written. Add no fact, number, cause or instruction.",
                "messages": [{"role": "user", "content": f"Question: {question}\n\nAnswer: {answer}"}],
            },
            headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
        )
        r.raise_for_status()
        text = "".join(c.get("text", "") for c in r.json()["content"] if c["type"] == "text").strip()
        return text if text and grounded(text, answer) else answer
