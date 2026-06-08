"""Unit tests for chunk → S3 key mapping and storage."""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from rag_aws.etl.chunking.storage import chunk_key, write_chunks_to_s3
from rag_aws.etl.interfaces import Chunk

BUCKET = "chunk-bucket"


def test_chunk_key_drops_extension_and_uses_index() -> None:
    assert chunk_key("repo", "guide/intro.md", 3) == "corpus/chunks/repo/guide/intro/3.txt"


def test_chunk_key_handles_top_level_doc() -> None:
    assert chunk_key("repo", "Welcome.md", 0) == "corpus/chunks/repo/Welcome/0.txt"


@pytest.fixture
def s3_client() -> Iterator[S3Client]:
    with mock_aws():
        client = boto3.client("s3", region_name="eu-west-1")
        client.create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "eu-west-1"}
        )
        yield client


def test_write_chunks_to_s3_writes_each_chunk(s3_client: S3Client) -> None:
    chunks = [
        Chunk(
            chunk_id=Chunk.make_id("r", "d.md", i),
            text=f"chunk {i}",
            source_doc="d.md",
            repo="r",
            chunk_index=i,
            char_start=0,
            char_end=1,
            token_count=2,
        )
        for i in range(2)
    ]
    keys = write_chunks_to_s3(s3_client, BUCKET, chunks)

    assert keys == ["corpus/chunks/r/d/0.txt", "corpus/chunks/r/d/1.txt"]
    body = s3_client.get_object(Bucket=BUCKET, Key=keys[0])["Body"].read()
    assert body == b"chunk 0"
