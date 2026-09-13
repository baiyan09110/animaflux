from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from .circadian import CircadianPolicy
from .models import Appraisal, MemoryInfluence, StateDelta, Transition, normalize_state
from .storage import StateStore


class Evaluator(Protocol):
    def evaluate(
        self,
        event: str,
        previous_state: dict,
        memory: MemoryInfluence,
    ) -> tuple[Appraisal, StateDelta]: ...


def _default_dynamics() -> dict[str, dict[str, tuple[float, float]]]:
    return {
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
        "relationship": {"unresolved_tension": (0.0, 72.0)},
        "self_state": {"self_presence": (5.0, 168.0)},
        "shared_history": {"salience": (0.0, 720.0)},
    }


@dataclass(slots=True)
class TransitionPolicy:
    value_min: float = 0.0
    value_max: float = 10.0
    delta_min: float = -2.0
    delta_max: float = 2.0
    dynamics: dict[str, dict[str, tuple[float, float]]] = field(default_factory=_default_dynamics)


def _toward(value: float, target: float, hours: float, half_life: float) -> float:
    return round(target + (value - target) * (0.5 ** (max(0.0, hours) / half_life)), 3)


def _clamp(value: float, low: float = 0.0, high: float = 10.0) -> float:
    return round(max(low, min(high, float(value))), 3)


class StateEngine:
    """Provider-neutral transition pipeline with explicit ordering and audit events."""

    def __init__(
        self,
        store: StateStore,
        evaluator: Evaluator,
        policy: TransitionPolicy | None = None,
        circadian_policy: CircadianPolicy | None = None,
    ):
        self.store = store
        self.evaluator = evaluator
        self.policy = policy or TransitionPolicy()
        self.circadian_policy = circadian_policy

    def current(self) -> dict:
        state = self.store.load_state()
        normalized = normalize_state(state)
        if state != normalized:
            state = normalized
            self.store.save_state(state)
        return normalized

    def decayed(self, state: dict, now: datetime | None = None) -> dict:
        result = copy.deepcopy(state)
        now = now or datetime.now(UTC)
        then = datetime.fromisoformat(result["updated_at"])
        hours = max(0.0, (now - then).total_seconds() / 3600)
        for group, values in self.policy.dynamics.items():
            for name, (target, half_life) in values.items():
                if name in result.get(group, {}):
                    result[group][name] = _toward(result[group][name], target, hours, half_life)
        result["updated_at"] = now.isoformat()
        return result

    def apply(self, state: dict, delta: StateDelta, now: datetime | None = None) -> dict:
        result = copy.deepcopy(state)
        for group, changes in delta.values.items():
            if group not in result or not isinstance(result[group], dict):
                continue
            for name, change in changes.items():
                if name in result[group] and isinstance(result[group][name], (int, float)):
                    bounded_change = _clamp(
                        change,
                        self.policy.delta_min,
                        self.policy.delta_max,
                    )
                    result[group][name] = _clamp(
                        result[group][name] + bounded_change,
                        self.policy.value_min,
                        self.policy.value_max,
                    )
        result["updated_at"] = (now or datetime.now(UTC)).isoformat()
        return result

    def bounded_delta(self, state: dict, delta: StateDelta) -> StateDelta:
        values: dict[str, dict[str, float]] = {}
        for group, changes in delta.values.items():
            if group not in state or not isinstance(state[group], dict):
                continue
            accepted = {
                name: _clamp(change, self.policy.delta_min, self.policy.delta_max)
                for name, change in changes.items()
                if name in state[group] and isinstance(state[group][name], (int, float))
            }
            if accepted:
                values[group] = accepted
        return StateDelta(values)

    def process(
        self,
        event: str,
        memory: MemoryInfluence | None = None,
        *,
        event_id: str | None = None,
        now: datetime | None = None,
        interaction_count: int = 0,
        late_interaction: bool = False,
    ) -> Transition:
        if event_id:
            existing = self.store.transition_by_event_id(event_id)
            if existing:
                return Transition.from_dict(existing)
        memory = memory or MemoryInfluence()
        now = now or datetime.now(UTC)
        previous = self.decayed(self.current(), now)
        self._apply_circadian(previous, now, interaction_count, late_interaction)
        appraisal, proposed = self.evaluator.evaluate(event, copy.deepcopy(previous), memory)
        applied = self.bounded_delta(previous, proposed)
        next_state = self.apply(previous, applied, now)
        notes = self._policy_notes(proposed, applied)
        transition = Transition(
            transition_id=str(uuid4()),
            created_at=now.isoformat(),
            event=event,
            event_id=event_id,
            appraisal=appraisal,
            previous_state=previous,
            proposed_delta=copy.deepcopy(proposed.values),
            applied_delta=applied.values,
            next_state=next_state,
            policy_notes=notes,
            memory_refs=memory.event_refs,
        )
        self.store.commit_transition(next_state, transition.to_dict())
        return transition

    def _apply_circadian(
        self, state: dict, now: datetime, interaction_count: int, late_interaction: bool
    ) -> None:
        if self.circadian_policy is None:
            return
        circadian = state["circadian"]
        local = self.circadian_policy.local_time(now)
        date_key = local.date().isoformat()
        offset, recovered_on = self.circadian_policy.recover_elapsed(
            int(circadian["schedule_offset_minutes"]),
            circadian.get("last_recovery_date"),
            date_key,
        )
        if late_interaction:
            offset = self.circadian_policy.after_late_interaction(offset)
        minute = local.hour * 60 + local.minute
        phase = self.circadian_policy.phase_at(minute, offset)
        phase = self.circadian_policy.phase_after_interaction(phase, interaction_count)
        if phase != circadian.get("phase"):
            circadian["changed_at"] = now.isoformat()
        circadian.update(
            phase=phase,
            schedule_offset_minutes=offset,
            last_recovery_date=recovered_on,
        )

    def _policy_notes(self, proposed: StateDelta, applied: StateDelta) -> list[str]:
        notes: list[str] = []
        for group, changes in proposed.values.items():
            for name, value in changes.items():
                accepted = applied.values.get(group, {}).get(name)
                path = f"{group}.{name}"
                if accepted is None:
                    notes.append(f"ignored unknown or non-numeric field: {path}")
                elif accepted != value:
                    notes.append(f"clamped {path}: {value} -> {accepted}")
        return notes
