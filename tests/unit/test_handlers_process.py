"""Unit tests for the per-document process handler (moto S3 + fakes)."""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from rag_aws.etl.chunking.chunker import NaiveChunker
from rag_aws.etl.embedding.fake import FakeEmbedder
from rag_aws.etl.handlers.process import process_item
from rag_aws.etl.indexing.memory_index import InMemoryVectorIndex
from rag_aws.etl.interfaces import TokenCounter

BUCKET = "proc-bucket"
RAW_KEY = "corpus/raw/amazon-s3-userguide/s3/intro.md"


class WordCounter(TokenCounter):
    def count_tokens(self, text: str) -> int:
        return len(text.split())


@pytest.fixture
def s3_client() -> Iterator[S3Client]:
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
        )
        yield client


def _chunker() -> NaiveChunker:
    return NaiveChunker(token_counter=WordCounter(), chunk_size_tokens=8, chunk_overlap_tokens=1)


def test_created_event_indexes_document(s3_client: S3Client) -> None:
    text = " ".join(f"word{i}" for i in range(40))
    s3_client.put_object(Bucket=BUCKET, Key=RAW_KEY, Body=text.encode("utf-8"))
    index = InMemoryVectorIndex()

    result = process_item(
        {"bucket": BUCKET, "key": RAW_KEY, "action": "created"},
        s3_client=s3_client,
        chunker=_chunker(),
        embedder=FakeEmbedder(dimensions=8),
        index=index,
    )

    assert result["action"] == "indexed"
    assert result["chunks"] == index.count() > 0
    # Chunk text was written to prefix B.
    chunks = s3_client.list_objects_v2(Bucket=BUCKET, Prefix="corpus/chunks/")
    assert chunks.get("KeyCount", 0) > 0


def test_removed_event_deletes_document(s3_client: S3Client) -> None:
    text = " ".join(f"word{i}" for i in range(40))
    s3_client.put_object(Bucket=BUCKET, Key=RAW_KEY, Body=text.encode("utf-8"))
    index = InMemoryVectorIndex()
    process_item(
        {"bucket": BUCKET, "key": RAW_KEY, "action": "created"},
        s3_client=s3_client,
        chunker=_chunker(),
        embedder=FakeEmbedder(dimensions=8),
        index=index,
    )
    assert index.count() > 0

    result = process_item(
        {"bucket": BUCKET, "key": RAW_KEY, "action": "removed"},
        s3_client=s3_client,
        chunker=_chunker(),
        embedder=FakeEmbedder(dimensions=8),
        index=index,
    )

    assert result["action"] == "deleted"
    assert index.count() == 0
    assert s3_client.list_objects_v2(Bucket=BUCKET, Prefix="corpus/chunks/").get("KeyCount", 0) == 0
