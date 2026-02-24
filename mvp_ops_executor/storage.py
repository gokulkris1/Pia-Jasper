from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SQLiteStorage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    user TEXT NOT NULL,
                    raw_message TEXT NOT NULL,
                    parsed_json TEXT,
                    status TEXT NOT NULL,
                    operation TEXT
                );

                CREATE TABLE IF NOT EXISTS request_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (request_id) REFERENCES requests(id)
                );

                CREATE INDEX IF NOT EXISTS idx_requests_user_status
                    ON requests(user, status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_request_events_request
                    ON request_events(request_id, ts ASC);
                """
            )
            conn.commit()

    def create_request(
        self,
        request_id: str,
        user: str,
        raw_message: str,
        parsed_json: str,
        status: str,
        operation: Optional[str],
    ) -> None:
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO requests (id, created_at, updated_at, user, raw_message, parsed_json, status, operation)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (request_id, now, now, user, raw_message, parsed_json, status, operation),
            )
            conn.commit()

    def update_request(self, request_id: str, **fields: Any) -> None:
        if not fields:
            return
        allowed = {"parsed_json", "status", "operation", "raw_message", "user"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        updates["updated_at"] = utc_now_iso()
        keys = list(updates.keys())
        set_clause = ", ".join(f"{k} = ?" for k in keys)
        params = [updates[k] for k in keys]
        params.append(request_id)
        with self._lock, self._connect() as conn:
            conn.execute(f"UPDATE requests SET {set_clause} WHERE id = ?", params)
            conn.commit()

    def append_event(self, request_id: str, stage: str, payload: Dict[str, Any]) -> int:
        payload_json = json.dumps(payload, sort_keys=True)
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO request_events (request_id, ts, stage, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (request_id, now, stage, payload_json),
            )
            conn.commit()
            return int(cur.lastrowid)

    def list_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id, created_at, updated_at, user, raw_message, parsed_json, status, operation
                FROM requests
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id, created_at, updated_at, user, raw_message, parsed_json, status, operation
                FROM requests
                WHERE id = ?
                """,
                (request_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_events(self, request_id: str) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.execute(
                """
                SELECT id, request_id, ts, stage, payload_json
                FROM request_events
                WHERE request_id = ?
                ORDER BY id ASC
                """,
                (request_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def find_latest_request_by_user(
        self, user: str, statuses: Optional[Iterable[str]] = None
    ) -> Optional[Dict[str, Any]]:
        query = """
            SELECT id, created_at, updated_at, user, raw_message, parsed_json, status, operation
            FROM requests
            WHERE user = ?
        """
        params: List[Any] = [user]
        if statuses:
            status_list = list(statuses)
            placeholders = ", ".join("?" for _ in status_list)
            query += f" AND status IN ({placeholders})"
            params.extend(status_list)
        query += " ORDER BY created_at DESC LIMIT 1"
        with self._connect() as conn:
            cur = conn.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def new_request_id(self) -> str:
        return str(uuid.uuid4())
