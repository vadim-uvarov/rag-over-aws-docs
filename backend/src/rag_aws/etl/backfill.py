"""Backfill: enqueue every object in ``corpus/raw/`` for processing.

For the first bulk load we don't want thousands of concurrent executions or
Bedrock throttling, so we push EventBridge-shaped "Object Created" events onto
the same SQS buffer the live pipeline uses, in controlled batches.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any, Protocol

from rag_aws.config.settings import RAW_PREFIX
from rag_aws.etl.handlers.events import _CREATED_DETAIL_TYPE

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

_SQS_BATCH_LIMIT = 10  # SendMessageBatch hard limit


class SqsClient(Protocol):
    """Minimal structural type for the part of the SQS client we use."""

    def send_message_batch(self, *, QueueUrl: str, Entries: list[dict[str, Any]]) -> Any: ...  # noqa: N803


def iter_raw_keys(s3_client: S3Client, bucket: str) -> Iterator[str]:
    """Yield every object key under ``corpus/raw/`` (paginated)."""
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=RAW_PREFIX):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def make_created_event_body(bucket: str, key: str) -> str:
    """Build an EventBridge-shaped 'Object Created' body (matches the live path)."""
    return json.dumps(
        {
            "detail-type": _CREATED_DETAIL_TYPE,
            "source": "aws.s3",
            "detail": {"bucket": {"name": bucket}, "object": {"key": key}},
        }
    )


def enqueue_backfill(
    s3_client: S3Client,
    sqs_client: SqsClient,
    *,
    bucket: str,
    queue_url: str,
    inter_batch_delay_seconds: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Enqueue a created-event for every raw object; return the number enqueued.

    Messages are sent in batches of 10 (the SQS limit), with an optional pause
    between batches to keep downstream concurrency under control.
    """
    enqueued = 0
    for batch in _batched(iter_raw_keys(s3_client, bucket), _SQS_BATCH_LIMIT):
        entries = [
            {"Id": str(offset), "MessageBody": make_created_event_body(bucket, key)}
            for offset, key in enumerate(batch)
        ]
        sqs_client.send_message_batch(QueueUrl=queue_url, Entries=entries)
        enqueued += len(entries)
        if inter_batch_delay_seconds > 0:
            sleep(inter_batch_delay_seconds)
    return enqueued


def _batched(items: Iterator[str], size: int) -> Iterator[list[str]]:
    """Group ``items`` into lists of at most ``size`` (like itertools.batched)."""
    batch: list[str] = []
    for item in items:
        batch.append(item)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch
