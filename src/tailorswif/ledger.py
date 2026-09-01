"""Shot-level ledger.

At phase 0 there are no training runs, so a SQLite file plus an object store is
plenty - Weights & Biases is overhead for a system that isn't training anything
yet.

The one number this exists to produce is `generations per usable shot`. Not the
per-second rate: that ratio is what decides the bill, documented productions run
it at five to nine, and driving it under two is the entire justification for
gating early. It is also the cleanest evidence that the taste layer does real work.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS takes (
    take_id       TEXT PRIMARY KEY,
    shot_id       TEXT NOT NULL,
    experiment    TEXT NOT NULL,
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    staging       TEXT,
    prompt        TEXT NOT NULL,
    path          TEXT,
    cost_usd      REAL NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'pending',
    reject_reason TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS takes_experiment ON takes(experiment);

CREATE TABLE IF NOT EXISTS comparisons (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    experiment TEXT NOT NULL,
    left_id    TEXT NOT NULL,
    right_id   TEXT NOT NULL,
    winner_id  TEXT,
    criterion  TEXT NOT NULL DEFAULT 'overall',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS comparisons_experiment ON comparisons(experiment);
"""


@dataclass(frozen=True, slots=True)
class Stats:
    takes: int
    usable: int
    rejected: int
    spend_usd: float

    @property
    def generations_per_usable_shot(self) -> float | None:
        """None until at least one take has been marked usable."""
        return round(self.takes / self.usable, 2) if self.usable else None


class Ledger:
    def __init__(self, path: str | Path = "runs/ledger.sqlite") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def record_take(
        self,
        *,
        take_id: str,
        shot_id: str,
        experiment: str,
        provider: str,
        model: str,
        prompt: str,
        staging: str | None = None,
        path: str | None = None,
        cost_usd: float = 0.0,
        status: str = "ok",
        reject_reason: str | None = None,
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """INSERT OR REPLACE INTO takes
                   (take_id, shot_id, experiment, provider, model, staging,
                    prompt, path, cost_usd, status, reject_reason)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (take_id, shot_id, experiment, provider, model, staging,
                 prompt, path, cost_usd, status, reject_reason),
            )

    def mark(self, take_id: str, status: str, reason: str | None = None) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE takes SET status = ?, reject_reason = ? WHERE take_id = ?",
                (status, reason, take_id),
            )

    def takes(self, experiment: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM takes"
        params: tuple = ()
        if experiment:
            query += " WHERE experiment = ?"
            params = (experiment,)
        query += " ORDER BY created_at, take_id"
        with closing(self._connect()) as conn:
            return list(conn.execute(query, params))

    def record_comparison(
        self,
        *,
        experiment: str,
        left_id: str,
        right_id: str,
        winner_id: str | None,
        criterion: str = "overall",
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """INSERT INTO comparisons
                   (experiment, left_id, right_id, winner_id, criterion)
                   VALUES (?,?,?,?,?)""",
                (experiment, left_id, right_id, winner_id, criterion),
            )

    def comparisons(self, experiment: str | None = None) -> list[sqlite3.Row]:
        query = "SELECT * FROM comparisons"
        params: tuple = ()
        if experiment:
            query += " WHERE experiment = ?"
            params = (experiment,)
        query += " ORDER BY id"
        with closing(self._connect()) as conn:
            return list(conn.execute(query, params))

    def stats(self, experiment: str | None = None) -> Stats:
        rows = self.takes(experiment)
        return Stats(
            takes=len(rows),
            usable=sum(1 for r in rows if r["status"] == "ok"),
            rejected=sum(1 for r in rows if r["status"] == "rejected"),
            spend_usd=round(sum(r["cost_usd"] for r in rows), 4),
        )
