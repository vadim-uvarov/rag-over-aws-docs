"""ISO-8601 UTC timestamp helpers.

Project convention: every timestamp is ISO-8601 in UTC, with millisecond
precision and a trailing ``Z`` (for example ``2026-06-08T12:34:56.789Z``).
"""

from __future__ import annotations

from datetime import UTC, datetime


def format_timestamp(moment: datetime | None = None) -> str:
    """Format a moment as ISO-8601 UTC with millisecond precision and a trailing ``Z``.

    Args:
        moment: The moment to format. A naive datetime is assumed to already be
            in UTC; an aware datetime is converted to UTC. Defaults to the
            current time.

    Returns:
        A string like ``2026-06-08T12:34:56.789Z``. Sub-millisecond precision is
        truncated (floored), and the millisecond field is always zero-padded to
        three digits.
    """
    if moment is None:
        moment = datetime.now(UTC)
    elif moment.tzinfo is None:
        # Treat a naive datetime as UTC rather than guessing the local zone.
        moment = moment.replace(tzinfo=UTC)

    moment = moment.astimezone(UTC)
    milliseconds = moment.microsecond // 1000  # floor microseconds to milliseconds
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{milliseconds:03d}Z"
