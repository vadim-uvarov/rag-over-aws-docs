"""Integration test: chunk → embed → index on a sample document.

Chunk text is persisted to moto S3 (prefix B); embedding uses the fake embedder;
indexing uses the in-memory index (and LanceDB where available).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from rag_aws.etl.chunking.chunker import NaiveChunker
from rag_aws.etl.embedding.fake import FakeEmbedder
from rag_aws.etl.indexing.memory_index import InMemoryVectorIndex
from rag_aws.etl.interfaces import TokenCounter, VectorIndex
from rag_aws.etl.pipeline import process_document

BUCKET = "etl-bucket"
DIMENSIONS = 16

SAMPLE_DOC = (
    "Amazon S3 stores objects in buckets. "
    "A bucket is a container for objects. "
    "You can configure lifecycle rules to expire old object versions. "
    "Server-side encryption protects data at rest. "
) * 4


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


def _index_factories(tmp_path: Path) -> list[tuple[str, VectorIndex]]:
    indexes: list[tuple[str, VectorIndex]] = [("memory", InMemoryVectorIndex())]
    if importlib.util.find_spec("lancedb") is not None:
        from rag_aws.etl.indexing.lancedb_index import LanceDBIndex

        indexes.append(("lancedb", LanceDBIndex(str(tmp_path / "ldb"), dimensions=DIMENSIONS)))
    return indexes


def test_pipeline_chunks_to_s3_embeds_and_indexes(s3_client: S3Client, tmp_path: Path) -> None:
    chunker = NaiveChunker(
        token_counter=WordCounter(), chunk_size_tokens=12, chunk_overlap_tokens=2
    )
    embedder = FakeEmbedder(dimensions=DIMENSIONS)

    for label, index in _index_factories(tmp_path):
        embedded = process_document(
            SAMPLE_DOC,
            source_doc="s3/intro.md",
            repo="amazon-s3-userguide",
            chunker=chunker,
            embedder=embedder,
            index=index,
            s3_client=s3_client,
            bucket=BUCKET,
        )
        assert embedded, f"{label}: expected at least one chunk"
        assert index.count() == len(embedded), label

        # Chunk text was written to prefix B.
        listing = s3_client.list_objects_v2(Bucket=BUCKET, Prefix="corpus/chunks/")
        assert listing.get("KeyCount", 0) >= len(embedded), label

        # A query built from the first chunk retrieves that chunk at the top.
        query_vector = embedder.embed_texts([embedded[0].chunk.text])[0]
        results = index.search(query_vector, top_k=3)
        assert results[0].chunk_id == embedded[0].chunk.chunk_id, label
        assert results[0].score > 0.9, label


def test_reindexing_a_document_replaces_its_chunks(s3_client: S3Client, tmp_path: Path) -> None:
    chunker = NaiveChunker(
        token_counter=WordCounter(), chunk_size_tokens=12, chunk_overlap_tokens=2
    )
    embedder = FakeEmbedder(dimensions=DIMENSIONS)
    index = InMemoryVectorIndex()

    process_document(
        SAMPLE_DOC,
        source_doc="s3/intro.md",
        repo="r",
        chunker=chunker,
        embedder=embedder,
        index=index,
    )
    first_count = index.count()
    # Re-running with shorter content must not accumulate stale chunks.
    process_document(
        "Amazon S3 stores objects.",
        source_doc="s3/intro.md",
        repo="r",
        chunker=chunker,
        embedder=embedder,
        index=index,
    )
    assert index.count() < first_count
