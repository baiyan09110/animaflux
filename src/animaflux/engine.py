from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from .models import AgentState, Appraisal, MemoryInfluence, StateDelta, Transition, utc_now
from .storage import StateStore


class Evaluator(Protocol):
    def evaluate(
        self,
        event: str,
        previous_state: dict,
        memory: MemoryInfluence,
    ) -> tuple[Appraisal, StateDelta]: ...


DEFAULT_DYNAMICS = {
    "emotion": {
        "happiness": (5.0, 24.0),
        "sadness": (0.0, 36.0),
        "anger": (0.0, 6.0),
        "anxiety": (0.0, 18.0),
        "fatigue": (0.0, 12.0),
    },
    "inner": {
        "vulnerability": (3.0, 18.0),
        "sharing_urge": (4.0, 10.0),
        "sleepiness": (2.0, 4.0),
        "energy": (6.0, 12.0),
    },
}


def _toward(value: float, target: float, hours: float, half_life: float) -> float:
    return round(target + (value - target) * (0.5 ** (max(0.0, hours) / half_life)), 3)


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return round(max(low, min(high, float(value))), 3)


class StateEngine:
    """Provider-neutral transition pipeline with explicit ordering and audit events."""

    def __init__(self, store: StateStore, evaluator: Evaluator):
        self.store = store
        self.evaluator = evaluator

    def current(self) -> dict:
        state = self.store.load_state()
        if state is None:
            state = AgentState().to_dict()
            self.store.save_state(state)
        return state

    def decayed(self, state: dict, now: datetime | None = None) -> dict:
        result = copy.deepcopy(state)
        now = now or datetime.now(timezone.utc)
        then = datetime.fromisoformat(state["updated_at"].replace("Z", "+00:00"))
        hours = max(0.0, (now - then).total_seconds() / 3600)
        for group, values in DEFAULT_DYNAMICS.items():
            for name, (target, half_life) in values.items():
                result[group][name] = _toward(result[group][name], target, hours, half_life)
        result["updated_at"] = now.isoformat()
        return result

    def apply(self, state: dict, delta: StateDelta) -> dict:
        result = copy.deepcopy(state)
        for group, changes in delta.values.items():
            if group not in result or not isinstance(result[group], dict):
                continue
            for name, change in changes.items():
                if name in result[group] and isinstance(result[group][name], (int, float)):
                    result[group][name] = _clamp(result[group][name] + _clamp(change, -2, 2))
        result["updated_at"] = utc_now()
        return result

    def bounded_delta(self, state: dict, delta: StateDelta) -> StateDelta:
        values: dict[str, dict[str, float]] = {}
        for group, changes in delta.values.items():
            if group not in state or not isinstance(state[group], dict):
                continue
            accepted = {
                name: _clamp(change, -2, 2)
                for name, change in changes.items()
                if name in state[group] and isinstance(state[group][name], (int, float))
            }
            if accepted:
                values[group] = accepted
        return StateDelta(values)

    def process(self, event: str, memory: MemoryInfluence | None = None) -> Transition:
        memory = memory or MemoryInfluence()
        previous = self.decayed(self.current())
        appraisal, proposed = self.evaluator.evaluate(event, copy.deepcopy(previous), memory)
        applied = self.bounded_delta(previous, proposed)
        next_state = self.apply(previous, applied)
        transition = Transition(
            transition_id=str(uuid4()),
            created_at=utc_now(),
            event=event,
            appraisal=appraisal,
            previous_state=previous,
            applied_delta=applied.values,
            next_state=next_state,
            memory_refs=memory.event_refs,
        )
        self.store.save_state(next_state)
        self.store.append_transition(transition.to_dict())
        return transition
