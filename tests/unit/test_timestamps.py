"""Unit tests for the ISO-8601 UTC timestamp helper."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone

from rag_aws.config import format_timestamp

_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_format_timestamp_default_is_well_formed() -> None:
    """Smoke test: the no-arg call returns a string in the project format."""
    assert _TIMESTAMP_PATTERN.match(format_timestamp())


def test_format_timestamp_formats_a_known_moment() -> None:
    moment = datetime(2026, 6, 8, 12, 34, 56, 789_000, tzinfo=UTC)
    assert format_timestamp(moment) == "2026-06-08T12:34:56.789Z"


def test_format_timestamp_pads_milliseconds_to_three_digits() -> None:
    # 5 ms must render as ".005", not ".5".
    moment = datetime(2026, 1, 1, 0, 0, 0, 5_000, tzinfo=UTC)
    assert format_timestamp(moment) == "2026-01-01T00:00:00.005Z"


def test_format_timestamp_truncates_sub_millisecond_precision() -> None:
    # 789_999 microseconds floors to 789 milliseconds.
    moment = datetime(2026, 1, 1, 0, 0, 0, 789_999, tzinfo=UTC)
    assert format_timestamp(moment) == "2026-01-01T00:00:00.789Z"


def test_format_timestamp_converts_aware_datetime_to_utc() -> None:
    # 14:00 at +02:00 is 12:00 UTC.
    plus_two = timezone(timedelta(hours=2))
    moment = datetime(2026, 6, 8, 14, 0, 0, tzinfo=plus_two)
    assert format_timestamp(moment) == "2026-06-08T12:00:00.000Z"


def test_format_timestamp_treats_naive_datetime_as_utc() -> None:
    moment = datetime(2026, 6, 8, 12, 0, 0)  # naive on purpose
    assert format_timestamp(moment) == "2026-06-08T12:00:00.000Z"
