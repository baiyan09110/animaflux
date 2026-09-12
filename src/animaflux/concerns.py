from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from math import exp, log

from .models import utc_now


class ConcernStatus(StrEnum):
    OPEN = "OPEN"
    EASING = "EASING"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class Grounding(StrEnum):
    EVIDENCE = "EVIDENCE"
    SUBJECTIVE = "SUBJECTIVE"


@dataclass(slots=True)
class Concern:
    key: str
    summary: str
    intensity: float
    status: ConcernStatus
    grounding: Grounding
    evidence_refs: list[str] = field(default_factory=list)
    resolution_refs: list[str] = field(default_factory=list)
    recurrence_count: int = 0
    activated_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        value = asdict(self)
        value["status"] = self.status.value
        value["grounding"] = self.grounding.value
        return value

    @classmethod
    def from_dict(cls, value: dict) -> "Concern":
        return cls(
            key=value["key"], summary=value["summary"], intensity=float(value["intensity"]),
            status=ConcernStatus(value["status"]), grounding=Grounding(value["grounding"]),
            evidence_refs=list(value.get("evidence_refs", [])),
            resolution_refs=list(value.get("resolution_refs", [])),
            recurrence_count=int(value.get("recurrence_count", 0)),
            activated_at=value.get("activated_at", utc_now()),
            updated_at=value.get("updated_at", utc_now()),
        )


@dataclass(slots=True)
class ConcernPolicy:
    min_confidence: float = 0.65
    easing_after_hours: float = 12.0
    easing_half_life_hours: float = 24.0
    max_evidence_refs: int = 24

    def activate(
        self, existing: Concern | None, *, key: str, summary: str,
        evidence_ref: str | None, confidence: float, intensity_delta: float,
        grounding: Grounding = Grounding.EVIDENCE, now: datetime | None = None,
    ) -> Concern | None:
        """Activate only grounded, confident evidence; repeated evidence is idempotent."""
        if not evidence_ref or confidence < self.min_confidence:
            return existing
        now_text = (now or datetime.now(timezone.utc)).isoformat()
        if existing is None:
            return Concern(
                key=key, summary=summary, intensity=self._clamp(max(0.5, intensity_delta)),
                status=ConcernStatus.OPEN, grounding=grounding, evidence_refs=[evidence_ref],
                activated_at=now_text, updated_at=now_text,
            )
        if existing.status == ConcernStatus.SUPPRESSED or evidence_ref in existing.evidence_refs:
            return existing
        reopened = existing.status == ConcernStatus.RESOLVED
        existing.status = ConcernStatus.OPEN
        existing.summary = summary
        existing.grounding = grounding
        existing.intensity = self._clamp(existing.intensity + min(1.5, max(0.0, intensity_delta)))
        existing.evidence_refs = (existing.evidence_refs + [evidence_ref])[-self.max_evidence_refs :]
        existing.updated_at = now_text
        existing.activated_at = now_text
        if reopened:
            existing.recurrence_count += 1
        return existing

    def advance_time(self, concern: Concern, now: datetime | None = None) -> Concern:
        """Silence may ease a concern, but can never prove that it was resolved."""
        if concern.status not in {ConcernStatus.OPEN, ConcernStatus.EASING}:
            return concern
        now = now or datetime.now(timezone.utc)
        then = datetime.fromisoformat(concern.updated_at.replace("Z", "+00:00"))
        quiet_hours = max(0.0, (now - then).total_seconds() / 3600)
        if concern.status == ConcernStatus.OPEN and quiet_hours < self.easing_after_hours:
            return concern
        decay_hours = (
            quiet_hours - self.easing_after_hours
            if concern.status == ConcernStatus.OPEN
            else quiet_hours
        )
        concern.status = ConcernStatus.EASING
        concern.intensity = round(
            concern.intensity * exp(-log(2) * decay_hours / self.easing_half_life_hours), 3
        )
        concern.updated_at = now.isoformat()
        return concern

    def resolve(self, concern: Concern, evidence_ref: str | None, now: datetime | None = None) -> Concern:
        if not evidence_ref:
            raise ValueError("resolution requires an evidence reference")
        concern.status = ConcernStatus.RESOLVED
        concern.intensity = 0.0
        concern.resolution_refs = (concern.resolution_refs + [evidence_ref])[-self.max_evidence_refs :]
        concern.updated_at = (now or datetime.now(timezone.utc)).isoformat()
        return concern

    def suppress(self, concern: Concern, now: datetime | None = None) -> Concern:
        concern.status = ConcernStatus.SUPPRESSED
        concern.updated_at = (now or datetime.now(timezone.utc)).isoformat()
        return concern

    @staticmethod
    def aggregate_intensity(concerns: list[Concern]) -> float:
        active = sorted(
            (c.intensity for c in concerns if c.status in {ConcernStatus.OPEN, ConcernStatus.EASING}),
            reverse=True,
        )
        return ConcernPolicy._clamp(active[0] + 0.2 * sum(active[1:])) if active else 0.0

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(10.0, float(value))), 3)
