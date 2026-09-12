from datetime import datetime, timedelta, timezone

import pytest

from animaflux import ConcernPolicy, ConcernStatus


def test_ungrounded_or_low_confidence_signal_cannot_create_concern():
    policy = ConcernPolicy()
    assert policy.activate(None, key="conflict", summary="possible friction", evidence_ref=None,
                           confidence=0.9, intensity_delta=2) is None
    assert policy.activate(None, key="conflict", summary="possible friction", evidence_ref="event-1",
                           confidence=0.4, intensity_delta=2) is None


def test_same_evidence_cannot_accumulate_pressure_twice():
    policy = ConcernPolicy()
    concern = policy.activate(None, key="conflict", summary="explicit disagreement",
                              evidence_ref="event-1", confidence=0.9, intensity_delta=2)
    repeated = policy.activate(concern, key="conflict", summary="explicit disagreement",
                               evidence_ref="event-1", confidence=0.9, intensity_delta=2)
    assert repeated is concern
    assert repeated.intensity == 2
    assert repeated.evidence_refs == ["event-1"]


def test_silence_eases_but_does_not_claim_resolution():
    policy = ConcernPolicy(easing_after_hours=12, easing_half_life_hours=24)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    concern = policy.activate(None, key="conflict", summary="explicit disagreement",
                              evidence_ref="event-1", confidence=0.9, intensity_delta=4, now=start)
    policy.advance_time(concern, start + timedelta(hours=36))
    assert concern.status == ConcernStatus.EASING
    assert concern.intensity == 2
    policy.advance_time(concern, start + timedelta(hours=60))
    assert concern.intensity == 1


def test_resolution_requires_evidence_and_recurrence_is_counted():
    policy = ConcernPolicy()
    concern = policy.activate(None, key="conflict", summary="explicit disagreement",
                              evidence_ref="event-1", confidence=0.9, intensity_delta=2)
    with pytest.raises(ValueError):
        policy.resolve(concern, None)
    policy.resolve(concern, "event-repair")
    reopened = policy.activate(concern, key="conflict", summary="same issue returned",
                               evidence_ref="event-2", confidence=0.9, intensity_delta=1)
    assert reopened.status == ConcernStatus.OPEN
    assert reopened.recurrence_count == 1
    assert reopened.intensity == 1


def test_aggregate_is_led_by_strongest_concern_not_raw_sum():
    policy = ConcernPolicy()
    first = policy.activate(None, key="a", summary="a", evidence_ref="a1",
                            confidence=1, intensity_delta=4)
    second = policy.activate(None, key="b", summary="b", evidence_ref="b1",
                             confidence=1, intensity_delta=3)
    assert policy.aggregate_intensity([first, second]) == 4.6
