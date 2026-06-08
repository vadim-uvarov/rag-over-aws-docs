"""Unit tests for EventBridge S3 event parsing."""

from __future__ import annotations

import pytest

from rag_aws.etl.handlers.events import (
    ACTION_CREATED,
    ACTION_REMOVED,
    parse_eventbridge_event,
)

_DETAIL = {"bucket": {"name": "my-bucket"}, "object": {"key": "corpus/raw/r/a.md"}}


def test_parses_object_created() -> None:
    event = parse_eventbridge_event("Object Created", _DETAIL)
    assert (event.bucket, event.key, event.action) == (
        "my-bucket",
        "corpus/raw/r/a.md",
        ACTION_CREATED,
    )


def test_parses_object_deleted() -> None:
    event = parse_eventbridge_event("Object Deleted", _DETAIL)
    assert event.action == ACTION_REMOVED


def test_rejects_unsupported_detail_type() -> None:
    with pytest.raises(ValueError, match="detail-type"):
        parse_eventbridge_event("Object Restore Completed", _DETAIL)
