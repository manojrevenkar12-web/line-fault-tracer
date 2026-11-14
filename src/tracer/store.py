"""One SQLite file holds the line, the knowledge graph and the clean time series. sql/schema.sql owns the model."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from .settings import ROOT


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript((ROOT / "sql" / "schema.sql").read_text())

    def q(self, sql: str, *args) -> list[tuple]:
        return self.db.execute(sql, args).fetchall()

    def one(self, sql: str, *args):
        row = self.db.execute(sql, args).fetchone()
        return row[0] if row else None

    # ------------------------------------------------------------------------------------------ the line

    def flow(self) -> list[str]:
        return [r[0] for r in self.q("SELECT id FROM assets ORDER BY position")]

    def asset_signals(self, asset: str) -> list[tuple[str, str]]:
        return self.q("SELECT id, unit FROM signals WHERE asset = ? ORDER BY id", asset)

    def signal_meta(self) -> dict[str, tuple[str, float, float]]:
        return {r[0]: (r[1], r[2], r[3]) for r in self.q("SELECT id, unit, lo, hi FROM signals")}

    # ------------------------------------------------------------------------------------------ time series

    def series(self, signal: str, t0: float, t1: float, as_of: float) -> tuple[np.ndarray, np.ndarray]:
        """Usable readings of one signal measured in [t0, t1) that the backend had received by `as_of`."""
        rows = self.q(
            "SELECT ts, value FROM samples WHERE signal = ? AND ts >= ? AND ts < ? AND recv_ts <= ? "
            "AND value IS NOT NULL AND quality NOT IN ('stuck') ORDER BY ts",
            signal,
            t0,
            t1,
            as_of,
        )
        if not rows:
            return np.empty(0), np.empty(0)
        a = np.array(rows, dtype=float)
        return a[:, 0], a[:, 1]

    def state_at(self, asset: str, ts: float, as_of: float) -> int | None:
        v = self.one(
            "SELECT value FROM samples WHERE signal = ? AND ts <= ? AND recv_ts <= ? AND value IS NOT NULL "
            "ORDER BY ts DESC LIMIT 1",
            f"{asset}.state",
            ts,
            as_of,
        )
        return None if v is None else int(round(v))

    def last_seen(self, asset: str, as_of: float) -> float | None:
        return self.one(
            "SELECT max(s.ts) FROM samples s JOIN signals g ON g.id = s.signal WHERE g.asset = ? AND s.recv_ts <= ?",
            asset,
            as_of,
        )

    def alarms(self, t0: float, t1: float, as_of: float) -> list[tuple[str, str, float, str]]:
        return self.q(
            "SELECT code, asset, ts, text FROM alarms WHERE ts >= ? AND ts <= ? AND recv_ts <= ? ORDER BY ts",
            t0,
            t1,
            as_of,
        )

    def counts(self) -> dict[str, int]:
        return dict(self.q("SELECT name, n FROM ingest_counts ORDER BY name"))
