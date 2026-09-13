from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
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
        self.event_index_path = self.directory / "event_index.jsonl"
        self._events_by_id: dict[str, dict[str, Any]] | None = None
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
        with self._lock:
            self._append_transition_unlocked(transition)

    def _append_transition_unlocked(self, transition: dict[str, Any]) -> None:
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(transition, ensure_ascii=False) + "\n")
        event_id = transition.get("event_id")
        if event_id:
            with self.event_index_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {"event_id": event_id, "transition": transition},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            if self._events_by_id is not None:
                self._events_by_id[event_id] = transition

    def commit_transition(self, state: dict[str, Any], transition: dict[str, Any]) -> None:
        """Best-effort single-process commit; use SQLite for crash atomicity."""
        with self._lock:
            self._save_state_unlocked(state)
            self._append_transition_unlocked(transition)

    def transition_by_event_id(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            if self._events_by_id is None:
                self._events_by_id = self._load_event_index_unlocked()
            return self._events_by_id.get(event_id)

    def _load_event_index_unlocked(self) -> dict[str, dict[str, Any]]:
        indexed: dict[str, dict[str, Any]] = {}
        if self.event_index_path.exists():
            for line in self.event_index_path.read_text(encoding="utf-8").splitlines():
                try:
                    row = json.loads(line)
                    if row.get("event_id") and isinstance(row.get("transition"), dict):
                        indexed[row["event_id"]] = row["transition"]
                except (json.JSONDecodeError, TypeError):
                    continue

        # Reconcile the append-only transition log once on startup. This both
        # upgrades pre-index stores and repairs a crash between the two appends.
        recovered: list[dict[str, Any]] = []
        if self.events_path.exists():
            for line in self.events_path.read_text(encoding="utf-8").splitlines():
                try:
                    transition = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_id = transition.get("event_id")
                if event_id and event_id not in indexed:
                    indexed[event_id] = transition
                    recovered.append({"event_id": event_id, "transition": transition})
        if recovered:
            with self.event_index_path.open("a", encoding="utf-8") as handle:
                for row in recovered:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return indexed

    def transitions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            if not self.events_path.exists():
                return []
            rows = self.events_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(row) for row in rows[-max(1, limit) :]][::-1]


class SQLiteStore(StateStore):
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._connection() as connection:
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
        connection = sqlite3.connect(self.path, isolation_level=None)
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def load_state(self) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM runtime_state WHERE singleton = 1"
            ).fetchone()
        return json.loads(row[0]) if row else None

    def save_state(self, state: dict[str, Any]) -> None:
        payload = json.dumps(state, ensure_ascii=False)
        with self._connection() as connection:
            connection.execute(
                "INSERT INTO runtime_state(singleton, payload) VALUES(1, ?) "
                "ON CONFLICT(singleton) DO UPDATE SET payload = excluded.payload",
                (payload,),
            )

    def append_transition(self, transition: dict[str, Any]) -> None:
        with self._connection() as connection:
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
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
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
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def transition_by_event_id(self, event_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload FROM transitions WHERE event_id = ?", (event_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def transitions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM transitions ORDER BY sequence DESC LIMIT ?",
                (max(1, limit),),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
