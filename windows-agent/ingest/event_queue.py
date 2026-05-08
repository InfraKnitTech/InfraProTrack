import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from utils.time_utils import utc_iso


class EventQueue:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT
                )
                """
            )

    def enqueue(self, event_type: str, payload: dict[str, Any], captured_at: str | None = None) -> None:
        event_id = str(uuid.uuid4())
        captured = captured_at or utc_iso()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO events(event_id, event_type, captured_at, payload) VALUES (?, ?, ?, ?)",
                (event_id, event_type, captured, json.dumps(payload)),
            )

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, event_id, event_type, captured_at, payload
                FROM events
                ORDER BY id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                "row_id": row[0],
                "event_id": row[1],
                "event_type": row[2],
                "captured_at": row[3],
                "payload": json.loads(row[4]),
            }
            for row in rows
        ]

    def delete(self, row_ids: list[int]) -> None:
        if not row_ids:
            return
        placeholders = ",".join("?" for _ in row_ids)
        with self._connect() as conn:
            conn.execute(f"DELETE FROM events WHERE id IN ({placeholders})", row_ids)

    def mark_failed(self, row_ids: list[int], error: str) -> None:
        if not row_ids:
            return
        placeholders = ",".join("?" for _ in row_ids)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE events SET attempts = attempts + 1, last_error = ? WHERE id IN ({placeholders})",
                [error, *row_ids],
            )
