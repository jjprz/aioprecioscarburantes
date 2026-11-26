"""Tests for the opening hours parser."""

from datetime import datetime

import pytest

from aioprecioscarburantes.models import TIMEZONE
from aioprecioscarburantes.schedule import next_change, parse_schedule


def at(day: int, hour: int, minute: int = 0) -> datetime:
    """Return a moment in the week of Monday 2026-11-23."""
    return datetime(2026, 11, 23 + day, hour, minute, tzinfo=TIMEZONE)


@pytest.mark.parametrize(
    ("text", "when", "expected"),
    [
        ("L-D: 24H", at(2, 3), True),
        ("L-D: 00:00-23:59", at(6, 23, 59), True),
        ("L-S: 07:00-22:00", at(5, 21, 59), True),
        ("L-S: 07:00-22:00", at(5, 22), False),
        ("L-S: 07:00-22:00", at(6, 12), False),
        ("L-S: 07:00-22:00; D: 08:00-14:00", at(6, 13), True),
        ("L-V: 07:00-14:00 y 16:00-21:00", at(1, 15), False),
        ("L-V: 07:00-14:00 y 16:00-21:00", at(1, 16), True),
        ("L-D: 7:00-23:00", at(0, 7), True),
        ("L-D: 06:00-00:00", at(0, 23, 30), True),
        ("L-D: 22:00-06:00", at(1, 5), True),
        ("L-D: 22:00-06:00", at(1, 12), False),
        ("L-J: 06:00-22:00; V-S: 24H; D: 08:00-22:00", at(5, 3), True),
    ],
)
def test_is_open(text: str, when: datetime, expected: bool) -> None:  # noqa: FBT001
    """Opening hours are understood."""
    schedule = parse_schedule(text)
    assert schedule is not None
    assert schedule.is_open(when) is expected


@pytest.mark.parametrize(
    "text",
    [
        "L: 24H",
        "",
        "Abierto",
        "L-D: 25:00-26:00",
        "L-D: 07:00-07:00",
        "D-L: 24H",
        "L-D",
    ],
)
def test_unknown(text: str) -> None:
    """Unknown or ambiguous formats give None."""
    assert parse_schedule(text) is None


def test_next_change() -> None:
    """The next opening or closing is found."""
    schedule = parse_schedule("L-S: 07:00-22:00")
    assert schedule is not None
    assert next_change(schedule, at(0, 12)) == at(0, 22)
    assert next_change(schedule, at(5, 23)) == at(7, 7)
    always = parse_schedule("L-D: 24H")
    assert always is not None
    assert always.always_open
    assert next_change(always, at(0, 12)) is None
