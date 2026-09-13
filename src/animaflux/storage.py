from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class StateStore(ABC):
    @abstractmethod
    def load_state(self) -> dict[str, Any] | None: ...

    @abstractmethod
    def save_state(self, state: dict[str, Any]) -> None: ...

    @abstractmethod
    def append_transition(self, transition: dict[str, Any]) -> None: ...

    @abstractmethod
    def commit_transition(self, state: dict[str, Any], transition: dict[str, Any]) -> None: ...

    @abstractmethod
    def transition_by_event_id(self, event_id: str) -> dict[str, Any] | None: ...

    @abstractmethod
    def transitions(self, limit: int = 100) -> list[dict[str, Any]]: ...


class JsonStore(StateStore):
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_path = self.directory / "state.json"
        self.events_path = self.directory / "transitions.jsonl"
        self._lock = threading.RLock()

    def load_state(self) -> dict[str, Any] | None:
        with self._lock:
            if not self.state_path.exists():
                return None
            return json.loads(self.state_path.read_text(encoding="utf-8"))

    def save_state(self, state: dict[str, Any]) -> None:
        with self._lock:
            self._save_state_unlocked(state)

    def _save_state_unlocked(self, state: dict[str, Any]) -> None:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.directory,
            prefix="state-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2)
            temporary = Path(handle.name)
        temporary.replace(self.state_path)

    def append_transition(self, transition: dict[str, Any]) -> None:
        with self._lock, self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(transition, ensure_ascii=False) + "\n")

    def commit_transition(self, state: dict[str, Any], transition: dict[str, Any]) -> None:
        """Best-effort single-process commit; use SQLite for crash atomicity."""
        with self._lock:
            self._save_state_unlocked(state)
            with self.events_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(transition, ensure_ascii=False) + "\n")

    def transition_by_event_id(self, event_id: str) -> dict[str, Any] | None:
        return next(
            (row for row in self.transitions(limit=10000) if row.get("event_id") == event_id),
            None,
        )

    def transitions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            if not self.events_path.exists():
                return []
            rows = self.events_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(row) for row in rows[-max(1, limit) :]][::-1]


class SQLiteStore(StateStore):
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transitions (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    transition_id TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL,
                    event_id TEXT,
                    payload TEXT NOT NULL
                );
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(transitions)")}
            if "event_id" not in columns:
                connection.execute("ALTER TABLE transitions ADD COLUMN event_id TEXT")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS transitions_event_id "
                "ON transitions(event_id) WHERE event_id IS NOT NULL"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def load_state(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM runtime_state WHERE singleton = 1"
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_state(self, state: dict[str, Any]) -> None:
        payload = json.dumps(state, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runtime_state(singleton, payload) VALUES(1, ?) "
                "ON CONFLICT(singleton) DO UPDATE SET payload = excluded.payload",
                (payload,),
            )

    def append_transition(self, transition: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO transitions(transition_id, created_at, event_id, payload) VALUES(?, ?, ?, ?)",
                (
                    transition["transition_id"],
                    transition["created_at"],
                    transition.get("event_id"),
                    json.dumps(transition, ensure_ascii=False),
                ),
            )

    def commit_transition(self, state: dict[str, Any], transition: dict[str, Any]) -> None:
        state_payload = json.dumps(state, ensure_ascii=False)
        transition_payload = json.dumps(transition, ensure_ascii=False)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO transitions(transition_id, created_at, event_id, payload) "
                "VALUES(?, ?, ?, ?)",
                (
                    transition["transition_id"],
                    transition["created_at"],
                    transition.get("event_id"),
                    transition_payload,
                ),
            )
            connection.execute(
                "INSERT INTO runtime_state(singleton, payload) VALUES(1, ?) "
                "ON CONFLICT(singleton) DO UPDATE SET payload = excluded.payload",
                (state_payload,),
            )

    def transition_by_event_id(self, event_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM transitions WHERE event_id = ?", (event_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def transitions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM transitions ORDER BY sequence DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
