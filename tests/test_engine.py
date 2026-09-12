from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    state["updated_at"] = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
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


def test_sleepiness_changes_observable_expression_form():
    state = AgentState().to_dict()
    state["inner"]["sleepiness"] = 9
    state["circadian"]["phase"] = "half_awake"
    texture = compile_expression(state)
    assert "sleepiness" in texture.reasons
    assert "extreme sleepiness" in texture.reasons
    assert "half_awake" in texture.reasons
