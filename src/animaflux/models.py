from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

CURRENT_SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class EmotionState:
    happiness: float = 5.0
    sadness: float = 0.0
    anger: float = 0.0
    anxiety: float = 0.0
    fatigue: float = 0.0


@dataclass(slots=True)
class RelationshipState:
    affection: float = 5.0
    trust: float = 5.0
    security: float = 5.0
    attachment_depth: float = 3.0
    familiarity: float = 1.0
    unresolved_tension: float = 0.0


@dataclass(slots=True)
class SelfState:
    self_presence: float = 5.0


@dataclass(slots=True)
class InnerState:
    vulnerability: float = 3.0
    sharing_urge: float = 4.0
    sleepiness: float = 2.0
    energy: float = 6.0


@dataclass(slots=True)
class CircadianState:
    phase: str = "awake"
    schedule_offset_minutes: int = 0
    changed_at: str = field(default_factory=utc_now)
    last_recovery_date: str | None = None


@dataclass(slots=True)
class SharedHistory:
    """A summary signal plus references; never a monotonically growing counter."""

    salience: float = 0.0
    memory_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentState:
    schema_version: int = CURRENT_SCHEMA_VERSION
    emotion: EmotionState = field(default_factory=EmotionState)
    relationship: RelationshipState = field(default_factory=RelationshipState)
    self_state: SelfState = field(default_factory=SelfState)
    inner: InnerState = field(default_factory=InnerState)
    circadian: CircadianState = field(default_factory=CircadianState)
    shared_history: SharedHistory = field(default_factory=SharedHistory)
    concerns: dict[str, dict[str, Any]] = field(default_factory=dict)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> AgentState:
        """Load old/partial persisted state by filling all missing fields."""
        value = normalize_state(value)
        return cls(
            schema_version=CURRENT_SCHEMA_VERSION,
            emotion=EmotionState(**_known(EmotionState, value.get("emotion", {}))),
            relationship=RelationshipState(
                **_known(RelationshipState, value.get("relationship", {}))
            ),
            self_state=SelfState(**_known(SelfState, value.get("self_state", {}))),
            inner=InnerState(**_known(InnerState, value.get("inner", {}))),
            circadian=CircadianState(**_known(CircadianState, value.get("circadian", {}))),
            shared_history=SharedHistory(**_known(SharedHistory, value.get("shared_history", {}))),
            concerns=dict(value.get("concerns", {})),
            updated_at=str(value.get("updated_at") or utc_now()),
        )


@dataclass(slots=True)
class Appraisal:
    meaning: str = ""
    importance: float = 0.0
    threat: float = 0.0
    uncertainty: float = 0.0
    self_involvement: float = 0.0


@dataclass(slots=True)
class MemoryInfluence:
    """Memory changes interpretation; it does not directly prescribe emotion."""

    event_refs: list[str] = field(default_factory=list)
    meaning_context: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StateDelta:
    values: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass(slots=True)
class Transition:
    transition_id: str
    created_at: str
    event: str
    event_id: str | None
    appraisal: Appraisal
    previous_state: dict[str, Any]
    proposed_delta: dict[str, dict[str, float]]
    applied_delta: dict[str, dict[str, float]]
    next_state: dict[str, Any]
    policy_notes: list[str] = field(default_factory=list)
    memory_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Transition:
        return cls(
            transition_id=value["transition_id"],
            created_at=value["created_at"],
            event=value["event"],
            event_id=value.get("event_id"),
            appraisal=Appraisal(**value.get("appraisal", {})),
            previous_state=value["previous_state"],
            proposed_delta=value.get("proposed_delta", value.get("applied_delta", {})),
            applied_delta=value.get("applied_delta", {}),
            next_state=value["next_state"],
            policy_notes=list(value.get("policy_notes", [])),
            memory_refs=list(value.get("memory_refs", [])),
        )


def _known(model: type, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    names = model.__dataclass_fields__
    return {key: item for key, item in value.items() if key in names}


def normalize_state(value: dict[str, Any] | None) -> dict[str, Any]:
    """Fill and type-check built-in fields while preserving host extensions."""
    defaults = AgentState().to_dict()
    normalized = _merge_defaults(defaults, value if isinstance(value, dict) else {})
    normalized["schema_version"] = CURRENT_SCHEMA_VERSION
    return normalized


def _merge_defaults(defaults: Any, value: Any) -> Any:
    if isinstance(defaults, dict):
        if not isinstance(value, dict):
            return copy.deepcopy(defaults)
        result = copy.deepcopy(value)
        for key, default in defaults.items():
            result[key] = _merge_defaults(default, value.get(key))
        return result
    if isinstance(defaults, list):
        return copy.deepcopy(value) if isinstance(value, list) else copy.deepcopy(defaults)
    if isinstance(defaults, float):
        return (
            float(value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else defaults
        )
    if isinstance(defaults, int):
        return (
            int(value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else defaults
        )
    if isinstance(defaults, str):
        return value if isinstance(value, str) else defaults
    return copy.deepcopy(value) if value is not None else copy.deepcopy(defaults)
