from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

PHASES = {"awake", "wind_down", "sleepy", "asleep", "half_awake", "waking"}


def in_window(minute: int, start: int, end: int) -> bool:
    return start <= minute < end if start < end else minute >= start or minute < end


@dataclass(slots=True)
class CircadianPolicy:
    sleep_minute: int = 60
    wake_minute: int = 450
    wind_down_minutes: int = 60
    max_schedule_offset: int = 180
    late_interaction_shift: int = 8
    daily_recovery: float = 0.75
    timezone_name: str | None = None

    def local_time(self, value: datetime) -> datetime:
        """Use an explicit IANA zone, or the host's local zone when omitted."""
        return (
            value.astimezone(ZoneInfo(self.timezone_name))
            if self.timezone_name
            else value.astimezone()
        )

    def phase_at(self, minute: int, offset: int = 0) -> str:
        offset = max(0, min(self.max_schedule_offset, offset))
        sleep = (self.sleep_minute + offset) % 1440
        wake = (self.wake_minute + offset) % 1440
        # Late interaction can delay actual sleep and the next wake time, but it
        # must not erase the sleep pressure that was already building.
        sleepy = (self.sleep_minute - min(30, max(10, self.wind_down_minutes // 2))) % 1440
        wind = (self.sleep_minute - self.wind_down_minutes) % 1440
        if in_window(minute, sleep, wake):
            return "asleep"
        if in_window(minute, sleepy, sleep):
            return "sleepy"
        if in_window(minute, wind, sleepy):
            return "wind_down"
        return "awake"

    def rouse(self, interactions: int) -> str:
        """A message rouses sleep; it never proves that the agent got up."""
        return "waking" if interactions >= 4 else "half_awake"

    def phase_after_interaction(self, phase: str, interactions: int) -> str:
        """Only an asleep agent is roused; ordinary late chat does not simulate waking."""
        if phase != "asleep":
            return phase
        return self.rouse(interactions)

    def after_late_interaction(self, offset: int) -> int:
        return min(self.max_schedule_offset, max(0, offset) + self.late_interaction_shift)

    def recover_next_day(self, offset: int) -> int:
        return max(0, int(min(self.max_schedule_offset, offset) * self.daily_recovery))

    def recover_elapsed(
        self, offset: int, last_recovery_date: str | None, date_key: str
    ) -> tuple[int, str]:
        """Apply one recovery step per elapsed local calendar day."""
        if last_recovery_date == date_key:
            return max(0, min(self.max_schedule_offset, offset)), date_key
        days = 1
        if last_recovery_date:
            try:
                days = max(
                    0, (date.fromisoformat(date_key) - date.fromisoformat(last_recovery_date)).days
                )
            except ValueError:
                days = 1
        bounded = max(0, min(self.max_schedule_offset, offset))
        return max(0, int(bounded * (self.daily_recovery**days))), date_key

    def recover_once(
        self, offset: int, last_recovery_date: str | None, date_key: str
    ) -> tuple[int, str]:
        """Backward-compatible alias for elapsed-day recovery."""
        return self.recover_elapsed(offset, last_recovery_date, date_key)
