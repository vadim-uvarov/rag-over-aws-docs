"""Unit tests for structured JSON logging."""

from __future__ import annotations

import json
import logging

from rag_aws.observability import JsonFormatter, get_logger


def _record(**kwargs: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    for key, value in kwargs.items():
        setattr(record, key, value)
    return record


def test_formats_core_fields_as_json() -> None:
    payload = json.loads(JsonFormatter().format(_record()))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "hello world"
    assert payload["timestamp"].endswith("Z")


def test_includes_extra_fields() -> None:
    payload = json.loads(JsonFormatter().format(_record(key="corpus/raw/r/a.md", chunks=3)))
    assert payload["key"] == "corpus/raw/r/a.md"
    assert payload["chunks"] == 3


def test_includes_exception_text() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record()
        record.exc_info = sys.exc_info()
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]


def test_get_logger_is_idempotent() -> None:
    first = get_logger("rag_aws.test.idempotent")
    second = get_logger("rag_aws.test.idempotent")
    assert first is second
    assert len(first.handlers) == 1
