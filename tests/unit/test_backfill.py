"""Unit tests for the backfill enqueuer (moto S3 + SQS)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from rag_aws.etl.backfill import enqueue_backfill, make_created_event_body
from rag_aws.etl.handlers.events import parse_eventbridge_event

BUCKET = "backfill-bucket"


@pytest.fixture
def aws() -> Iterator[tuple[S3Client, Any, str]]:
    with mock_aws():
        s3_client = boto3.client("s3", region_name="eu-west-1")
        s3_client.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
        )
        sqs_client = boto3.client("sqs", region_name="eu-west-1")
        queue_url = sqs_client.create_queue(QueueName="etl-ingest")["QueueUrl"]
        yield s3_client, sqs_client, queue_url


def _seed_raw_objects(s3_client: S3Client, count: int) -> None:
    for i in range(count):
        s3_client.put_object(Bucket=BUCKET, Key=f"corpus/raw/r/doc{i}.md", Body=b"x")
    # An object outside corpus/raw/ must be ignored.
    s3_client.put_object(Bucket=BUCKET, Key="web/index.html", Body=b"x")


def test_made_event_body_round_trips_to_created() -> None:
    body = json.loads(make_created_event_body(BUCKET, "corpus/raw/r/a.md"))
    event = parse_eventbridge_event(body["detail-type"], body["detail"])
    assert event.action == "created"
    assert event.key == "corpus/raw/r/a.md"


def test_enqueue_backfill_sends_one_message_per_raw_object(aws: tuple[S3Client, Any, str]) -> None:
    s3_client, sqs_client, queue_url = aws
    _seed_raw_objects(s3_client, count=3)

    enqueued = enqueue_backfill(s3_client, sqs_client, bucket=BUCKET, queue_url=queue_url)

    assert enqueued == 3  # web/index.html excluded
    attrs = sqs_client.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["ApproximateNumberOfMessages"]
    )
    assert int(attrs["Attributes"]["ApproximateNumberOfMessages"]) == 3


def test_enqueue_backfill_batches_beyond_sqs_limit(aws: tuple[S3Client, Any, str]) -> None:
    s3_client, sqs_client, queue_url = aws
    _seed_raw_objects(s3_client, count=23)  # > 2 full batches of 10

    enqueued = enqueue_backfill(s3_client, sqs_client, bucket=BUCKET, queue_url=queue_url)
    assert enqueued == 23
