"""Parse S3 EventBridge events into a normalized document event."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# EventBridge S3 detail-types we care about.
_CREATED_DETAIL_TYPE = "Object Created"
_REMOVED_DETAIL_TYPE = "Object Deleted"

ACTION_CREATED = "created"
ACTION_REMOVED = "removed"


@dataclass(frozen=True)
class DocumentEvent:
    """A normalized create/remove event for one S3 object.

    Attributes:
        bucket: Source bucket name.
        key: Object key.
        action: ``"created"`` or ``"removed"``.
    """

    bucket: str
    key: str
    action: str


def parse_eventbridge_event(detail_type: str, detail: dict[str, Any]) -> DocumentEvent:
    """Turn an EventBridge S3 event into a :class:`DocumentEvent`.

    Args:
        detail_type: The event's ``detail-type`` (e.g. ``"Object Created"``).
        detail: The event's ``detail`` payload.

    Raises:
        ValueError: If the detail-type is not a supported S3 object event.
    """
    if detail_type == _CREATED_DETAIL_TYPE:
        action = ACTION_CREATED
    elif detail_type == _REMOVED_DETAIL_TYPE:
        action = ACTION_REMOVED
    else:
        raise ValueError(f"Unsupported S3 EventBridge detail-type: {detail_type!r}")

    return DocumentEvent(
        bucket=detail["bucket"]["name"],
        key=detail["object"]["key"],
        action=action,
    )
