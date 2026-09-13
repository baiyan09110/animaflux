from __future__ import annotations

from datetime import UTC, datetime, timedelta

from animaflux import (
    AgentState,
    Appraisal,
    CircadianPolicy,
    JsonStore,
    MemoryInfluence,
    StateDelta,
    StateEngine,
    compile_expression,
)


class StubEvaluator:
    def evaluate(self, event, previous_state, memory):
        assert memory.meaning_context == ["A similar event was previously repaired."]
        return Appraisal(meaning="repair attempt", importance=7), StateDelta(
            {"emotion": {"anger": -1}, "relationship": {"trust": 0.25}}
        )


def test_decay_happens_before_appraisal_and_delta(tmp_path):
    store = JsonStore(tmp_path)
    state = AgentState().to_dict()
    state["emotion"]["anger"] = 8
    state["updated_at"] = (datetime.now(UTC) - timedelta(hours=6)).isoformat()
    store.save_state(state)

    transition = StateEngine(store, StubEvaluator()).process(
        "I want to repair this.",
        MemoryInfluence(meaning_context=["A similar event was previously repaired."]),
    )

    assert transition.previous_state["emotion"]["anger"] == 4
    assert transition.next_state["emotion"]["anger"] == 3
    assert transition.next_state["relationship"]["trust"] == 5.25
    assert store.transitions()[0]["transition_id"] == transition.transition_id


def test_circadian_messages_rouse_without_implying_getting_up():
    policy = CircadianPolicy()
    assert policy.rouse(1) == "half_awake"
    assert policy.rouse(4) == "waking"
    assert policy.after_late_interaction(176) == 180
    assert policy.recover_next_day(120) == 90
    assert policy.phase_after_interaction("wind_down", 9) == "wind_down"
    assert policy.phase_after_interaction("asleep", 1) == "half_awake"


def test_late_chat_delays_sleep_but_not_sleep_pressure():
    policy = CircadianPolicy(sleep_minute=60, wake_minute=450, wind_down_minutes=60)
    assert policy.phase_at(45, offset=120) == "sleepy"
    assert policy.phase_at(90, offset=120) == "sleepy"
    assert policy.phase_at(190, offset=120) == "asleep"


def test_sleepiness_changes_observable_expression_form():
    state = AgentState().to_dict()
    state["inner"]["sleepiness"] = 9
    state["circadian"]["phase"] = "half_awake"
    texture = compile_expression(state)
    assert "sleepiness" in texture.reasons
    assert "extreme sleepiness" in texture.reasons
    assert "half_awake" in texture.reasons
    assert any("fully awake" in rule for rule in texture.guidance)


def test_active_concern_produces_repair_guidance_without_forcing_repetition():
    state = AgentState().to_dict()
    state["relationship"]["unresolved_tension"] = 4
    state["concerns"]["conflict"] = {
        "summary": "a recent disagreement",
        "intensity": 5,
        "status": "OPEN",
    }
    texture = compile_expression(state)
    assert "active concern" in texture.reasons
    assert any("only when relevant" in rule for rule in texture.guidance)
