"""Opening hours of fuel stations, as published by the Ministry.

Examples: "L-D: 24H", "L-S: 07:00-22:00; D: 08:00-14:00",
"L-V: 07:00-14:00 y 16:00-21:00", "L-J: 06:00-22:00; V-S: 24H; D: 08:00-22:00".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import TIMEZONE

DAYS = "LMXJVSD"  # Monday to Sunday
_RANGE = re.compile(r"^(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})$")
_DAY_SPEC = re.compile(r"^([LMXJVSD])(?:-([LMXJVSD]))?$")


@dataclass(frozen=True, slots=True)
class Schedule:
    """Opening ranges per weekday (0 = Monday), in minutes from midnight."""

    ranges: dict[int, list[tuple[int, int]]]

    @property
    def always_open(self) -> bool:
        """Return if the station never closes."""
        return all(self.ranges.get(day) == [(0, 1440)] for day in range(7))

    def is_open(self, when: datetime) -> bool:
        """Return if the station is open at a moment."""
        local = when.astimezone(TIMEZONE)
        minute = local.hour * 60 + local.minute
        today = local.weekday()
        if any(start <= minute < end for start, end in self.ranges.get(today, [])):
            return True
        # A range of yesterday that goes past midnight
        yesterday = (today - 1) % 7
        return any(
            end > 1440 and minute < end - 1440
            for _, end in self.ranges.get(yesterday, [])
        )


def _minutes(hour: str, minute: str) -> int:
    value = int(hour) * 60 + int(minute)
    if value > 1440 or int(minute) >= 60:
        raise ValueError
    return value


def _parse_range(text: str) -> tuple[int, int]:
    """Parse "24H" or "07:00-22:00" into minutes; raise ValueError if unknown."""
    if text.upper() == "24H":
        return (0, 1440)
    if not (hours := _RANGE.match(text)):
        raise ValueError
    start = _minutes(hours[1], hours[2])
    end = _minutes(hours[3], hours[4])
    if end == start:
        raise ValueError
    if end < start or end == 0:
        end += 1440  # closes after midnight
    if end - start >= 1439:
        return (0, 1440)  # 00:00-23:59 means always open
    return (start, end)


def _parse_part(part: str) -> tuple[range, list[tuple[int, int]]]:
    """Parse "L-V: 07:00-14:00 y 16:00-21:00"; raise ValueError if unknown."""
    days_text, _, hours_text = part.strip().partition(":")
    match = _DAY_SPEC.match(days_text.strip())
    if not match or not hours_text.strip():
        raise ValueError
    first = DAYS.index(match[1])
    last = DAYS.index(match[2] or match[1])
    if last < first:
        raise ValueError
    ranges = [_parse_range(item.strip()) for item in hours_text.split(" y ")]
    return range(first, last + 1), ranges


def parse_schedule(text: str) -> Schedule | None:
    """Parse the Ministry's opening hours; None if the format is unknown.

    A lone "L" (Monday) is ambiguous: many stations open every day publish it,
    so a schedule that mentions no other day is not trusted.
    """
    ranges: dict[int, list[tuple[int, int]]] = {}
    try:
        for part in text.split(";"):
            days, day_ranges = _parse_part(part)
            for day in days:
                ranges.setdefault(day, []).extend(day_ranges)
    except ValueError:
        return None
    if not ranges or set(ranges) == {0}:
        return None
    return Schedule(ranges)


def next_change(schedule: Schedule, when: datetime) -> datetime | None:
    """Return when the station next opens or closes (None if it never does)."""
    if schedule.always_open:
        return None
    local = when.astimezone(TIMEZONE)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    current = schedule.is_open(local)
    candidates = sorted(
        midnight + timedelta(days=offset, minutes=minute)
        for offset in range(-1, 8)
        for start, end in schedule.ranges.get((local.weekday() + offset) % 7, [])
        for minute in (start, end)
    )
    for moment in candidates:
        if moment > local and schedule.is_open(moment) != current:
            return moment
    return None


__all__ = ["Schedule", "next_change", "parse_schedule"]
