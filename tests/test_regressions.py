from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from animaflux import (
    AgentState,
    Appraisal,
    CircadianPolicy,
    JsonStore,
    SQLiteStore,
    StateDelta,
    StateEngine,
    TransitionPolicy,
    compile_expression,
)


class CountingEvaluator:
    def __init__(self, change: float = 1):
        self.calls = 0
        self.change = change

    def evaluate(self, event, previous_state, memory):
        self.calls += 1
        return Appraisal(meaning=event), StateDelta(
            {"emotion": {"anger": self.change}, "missing": {"field": 2}}
        )


def test_small_circadian_offsets_recover_to_zero_and_only_once_per_day():
    policy = CircadianPolicy()
    offset, date = policy.recover_once(2, None, "2026-09-13")
    assert (offset, date) == (1, "2026-09-13")
    assert policy.recover_once(offset, date, "2026-09-13") == (1, date)
    assert policy.recover_once(offset, date, "2026-09-14") == (0, "2026-09-14")


def test_circadian_recovery_accounts_for_every_silent_day():
    policy = CircadianPolicy()
    assert policy.recover_elapsed(120, "2026-09-09", "2026-09-14") == (
        28,
        "2026-09-14",
    )


def test_partial_old_state_is_migrated_without_key_errors(tmp_path):
    store = JsonStore(tmp_path)
    store.save_state({"emotion": {"anger": 7}, "updated_at": "2026-09-13T00:00:00+00:00"})
    state = StateEngine(store, CountingEvaluator()).current()
    assert state["schema_version"] == 1
    assert state["emotion"]["anger"] == 7
    assert state["relationship"]["familiarity"] == 1
    assert state["circadian"]["last_recovery_date"] is None


def test_future_state_schema_is_rejected_instead_of_silently_downgraded(tmp_path):
    store = JsonStore(tmp_path)
    store.save_state({"schema_version": 99})
    with pytest.raises(ValueError, match="newer than supported"):
        StateEngine(store, CountingEvaluator()).current()


def test_engine_updates_circadian_phase_and_schedule_in_configured_timezone(tmp_path):
    evaluator = CountingEvaluator()
    store = JsonStore(tmp_path)
    state = AgentState().to_dict()
    state["circadian"]["schedule_offset_minutes"] = 4
    store.save_state(state)
    policy = CircadianPolicy(timezone_name="Asia/Shanghai")
    transition = StateEngine(store, evaluator, circadian_policy=policy).process(
        "late message",
        now=datetime(2026, 9, 13, 17, 30, tzinfo=UTC),
        interaction_count=1,
        late_interaction=True,
    )
    assert transition.previous_state["circadian"]["phase"] == "half_awake"
    assert transition.previous_state["circadian"]["schedule_offset_minutes"] == 11
    assert transition.previous_state["circadian"]["last_recovery_date"] == "2026-09-14"


def test_event_id_is_idempotent_and_proposed_delta_is_audited(tmp_path):
    evaluator = CountingEvaluator(change=5)
    engine = StateEngine(SQLiteStore(tmp_path / "state.db"), evaluator)
    first = engine.process("same delivery", event_id="telegram:update:42")
    second = engine.process("same delivery", event_id="telegram:update:42")
    assert evaluator.calls == 1
    assert first.transition_id == second.transition_id
    assert first.proposed_delta["emotion"]["anger"] == 5
    assert first.applied_delta["emotion"]["anger"] == 2
    assert "clamped emotion.anger: 5 -> 2.0" in first.policy_notes
    assert any("missing.field" in note for note in first.policy_notes)
    assert first.source_state is not None
    assert first.source_state["updated_at"] != first.previous_state["updated_at"]


def test_transition_policy_is_configurable(tmp_path):
    policy = TransitionPolicy(delta_min=-0.5, delta_max=0.5)
    transition = StateEngine(JsonStore(tmp_path), CountingEvaluator(change=4), policy).process(
        "bounded"
    )
    assert transition.applied_delta["emotion"]["anger"] == 0.5


def test_apply_defensively_bounds_a_direct_delta(tmp_path):
    engine = StateEngine(JsonStore(tmp_path), CountingEvaluator())
    state = AgentState().to_dict()
    next_state = engine.apply(state, StateDelta({"emotion": {"anger": 9}}))
    assert next_state["emotion"]["anger"] == 2


def test_state_normalization_preserves_extensions_and_repairs_bad_types(tmp_path):
    store = JsonStore(tmp_path)
    state = AgentState().to_dict()
    state["host_extension"] = {"private_mode": True}
    state["emotion"]["custom_affect"] = 8
    state["emotion"]["anger"] = "high"
    store.save_state(state)
    normalized = StateEngine(store, CountingEvaluator()).current()
    assert normalized["host_extension"] == {"private_mode": True}
    assert normalized["emotion"]["custom_affect"] == 8
    assert normalized["emotion"]["anger"] == 0


def test_json_idempotency_index_has_no_ten_thousand_event_window(tmp_path):
    target = {"event_id": "oldest", "transition_id": "oldest-transition"}
    rows = [target, *({"event_id": f"new-{index}"} for index in range(10_001))]
    (tmp_path / "transitions.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    store = JsonStore(tmp_path)
    assert store.transition_by_event_id("oldest") == target
    assert (tmp_path / "event_index.jsonl").exists()


def test_existing_sqlite_database_is_migrated(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE runtime_state (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                payload TEXT NOT NULL
            );
            CREATE TABLE transitions (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                transition_id TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            """
        )
    store = SQLiteStore(path)
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(transitions)")}
    assert "event_id" in columns
    StateEngine(store, CountingEvaluator()).process("after migration", event_id="old-db:1")
    assert store.transition_by_event_id("old-db:1") is not None


def test_expression_guidance_has_rule_and_character_budgets():
    state = AgentState().to_dict()
    state["emotion"].update(anger=8, sadness=8)
    state["relationship"]["unresolved_tension"] = 8
    state["inner"].update(sharing_urge=9, sleepiness=10)
    state["circadian"]["phase"] = "half_awake"
    state["concerns"]["conflict"] = {
        "status": "OPEN",
        "intensity": 8,
        "summary": "an unresolved argument",
    }
    texture = compile_expression(state)
    assert len(texture.guidance) <= 6
    assert sum(len(rule) + 2 for rule in texture.guidance) <= 1200
    assert texture.omitted_rules > 0
    assert any("Circadian state has priority" in rule for rule in texture.guidance)
