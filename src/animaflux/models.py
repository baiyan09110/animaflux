from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@dataclass(slots=True)
class SharedHistory:
    """A summary signal plus references; never a monotonically growing counter."""

    salience: float = 0.0
    memory_refs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AgentState:
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
    appraisal: Appraisal
    previous_state: dict[str, Any]
    applied_delta: dict[str, dict[str, float]]
    next_state: dict[str, Any]
    memory_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
