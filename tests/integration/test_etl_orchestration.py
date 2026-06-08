"""Integration test: simulate the EventBridge → SQS → dispatch → Map(process) flow.

Step Functions Local needs Java/Docker, so instead of running the real state
machine this test drives the same handler functions the Map state invokes:
backfill enqueues created-events, the dispatcher batches them into the Map input,
and ``process_item`` runs per item — proving a created file ends up indexed and a
removed file is deleted.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from rag_aws.etl.backfill import enqueue_backfill
from rag_aws.etl.chunking.chunker import NaiveChunker
from rag_aws.etl.embedding.fake import FakeEmbedder
from rag_aws.etl.handlers.dispatch import build_execution_input
from rag_aws.etl.handlers.process import process_item
from rag_aws.etl.indexing.memory_index import InMemoryVectorIndex
from rag_aws.etl.interfaces import TokenCounter

BUCKET = "orch-bucket"
DIMENSIONS = 8


class WordCounter(TokenCounter):
    def count_tokens(self, text: str) -> int:
        return len(text.split())


@pytest.fixture
def aws() -> Iterator[tuple[S3Client, Any, str]]:
    with mock_aws():
        s3_client = boto3.client("s3", region_name="eu-west-1")
        s3_client.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
        )
        sqs_client = boto3.client("sqs", region_name="eu-west-1")
        queue_url = sqs_client.create_queue(QueueName="ingest")["QueueUrl"]
        yield s3_client, sqs_client, queue_url


def _receive_as_sqs_records(sqs_client: Any, queue_url: str) -> list[dict[str, Any]]:
    """Drain the queue and shape messages like an SQS Lambda event's Records."""
    records: list[dict[str, Any]] = []
    while True:
        response = sqs_client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10)
        messages = response.get("Messages", [])
        if not messages:
            break
        for message in messages:
            records.append({"body": message["Body"]})
            sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
    return records


def test_backfill_then_dispatch_then_process_indexes_documents(
    aws: tuple[S3Client, Any, str],
) -> None:
    s3_client, sqs_client, queue_url = aws
    body = " ".join(f"word{i}" for i in range(30))
    for name in ("a.md", "b.md"):
        s3_client.put_object(Bucket=BUCKET, Key=f"corpus/raw/r/{name}", Body=body.encode("utf-8"))

    # Backfill enqueues; dispatcher turns the SQS batch into the Map input.
    enqueue_backfill(s3_client, sqs_client, bucket=BUCKET, queue_url=queue_url)
    payload = build_execution_input(_receive_as_sqs_records(sqs_client, queue_url))
    assert len(payload["items"]) == 2

    # The Map state would invoke process_item per item.
    index = InMemoryVectorIndex()
    chunker = NaiveChunker(token_counter=WordCounter(), chunk_size_tokens=8, chunk_overlap_tokens=1)
    embedder = FakeEmbedder(dimensions=DIMENSIONS)
    for item in payload["items"]:
        process_item(item, s3_client=s3_client, chunker=chunker, embedder=embedder, index=index)

    assert index.count() > 0
    assert {result.repo for result in index.search(embedder.embed_texts([body])[0], top_k=5)} == {
        "r"
    }


def test_removed_event_flows_through_to_deletion(aws: tuple[S3Client, Any, str]) -> None:
    s3_client, _sqs_client, _queue_url = aws
    body = " ".join(f"word{i}" for i in range(30))
    s3_client.put_object(Bucket=BUCKET, Key="corpus/raw/r/a.md", Body=body.encode("utf-8"))

    index = InMemoryVectorIndex()
    chunker = NaiveChunker(token_counter=WordCounter(), chunk_size_tokens=8, chunk_overlap_tokens=1)
    embedder = FakeEmbedder(dimensions=DIMENSIONS)
    process_item(
        {"bucket": BUCKET, "key": "corpus/raw/r/a.md", "action": "created"},
        s3_client=s3_client,
        chunker=chunker,
        embedder=embedder,
        index=index,
    )
    assert index.count() > 0

    # A delete event (as EventBridge would deliver) drives removal.
    process_item(
        {"bucket": BUCKET, "key": "corpus/raw/r/a.md", "action": "removed"},
        s3_client=s3_client,
        chunker=chunker,
        embedder=embedder,
        index=index,
    )
    assert index.count() == 0
