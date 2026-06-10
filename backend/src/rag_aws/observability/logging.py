"""Structured JSON logging for CloudWatch.

Emitting one JSON object per line lets CloudWatch Logs Insights query fields
directly. Timestamps follow the project convention (ISO-8601 UTC ms ``Z``).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from rag_aws.config.timestamps import format_timestamp

# Standard LogRecord attributes we don't echo as custom fields.
_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Render a log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": format_timestamp(datetime.fromtimestamp(record.created, tz=UTC)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any structured context passed via `extra={...}`.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger that emits structured JSON to stdout (idempotent setup)."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.propagate = False  # avoid duplicate lines via the root logger
    return logger
