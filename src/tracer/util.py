from __future__ import annotations

import hashlib
from datetime import date, timedelta

import numpy as np


def seeded(*keys) -> np.random.Generator:
    """The desk's own simulations: the same inputs give the same forecast."""
    h = hashlib.blake2b("/".join(map(str, ("tracer",) + keys)).encode(), digest_size=8).digest()
    return np.random.default_rng(int.from_bytes(h, "little"))


def iso(epoch: str, day: int) -> str:
    return (date.fromisoformat(epoch) + timedelta(days=int(day))).isoformat()


def day_of(epoch: str, when: str) -> int:
    return (date.fromisoformat(when) - date.fromisoformat(epoch)).days
