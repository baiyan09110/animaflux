from __future__ import annotations

import json
import sqlite3
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
            temporary = self.state_path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.state_path)

    def append_transition(self, transition: dict[str, Any]) -> None:
        with self._lock, self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(transition, ensure_ascii=False) + "\n")

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
                    payload TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
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
                "INSERT INTO transitions(transition_id, created_at, payload) VALUES(?, ?, ?)",
                (
                    transition["transition_id"],
                    transition["created_at"],
                    json.dumps(transition, ensure_ascii=False),
                ),
            )

    def transitions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM transitions ORDER BY sequence DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
