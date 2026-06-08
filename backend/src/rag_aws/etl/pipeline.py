"""Wire the ETL stages: chunk → (store text) → embed → index.

A thin orchestration helper reused by tests and by the Lambda handlers (PR4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rag_aws.etl.chunking.storage import write_chunks_to_s3
from rag_aws.etl.interfaces import Chunker, EmbeddedChunk, Embedder, VectorIndex

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


def process_document(
    text: str,
    *,
    source_doc: str,
    repo: str,
    chunker: Chunker,
    embedder: Embedder,
    index: VectorIndex,
    s3_client: S3Client | None = None,
    bucket: str | None = None,
) -> list[EmbeddedChunk]:
    """Chunk, embed, and index one document; optionally persist chunk text to S3.

    Re-indexing is safe: the document's existing chunks are deleted before the
    new ones are upserted, so updates and re-runs don't leave stale vectors.

    Args:
        text: Raw document text.
        source_doc: Repo-relative path of the document.
        repo: Source repo name.
        chunker: Chunking implementation.
        embedder: Embedding implementation.
        index: Vector index implementation.
        s3_client: If given with ``bucket``, chunk text is written to ``corpus/chunks/``.
        bucket: Project bucket name.

    Returns:
        The embedded chunks that were indexed.
    """
    chunks = chunker.chunk_document(text, source_doc=source_doc, repo=repo)
    if s3_client is not None and bucket is not None:
        write_chunks_to_s3(s3_client, bucket, chunks)

    vectors = embedder.embed_texts([chunk.text for chunk in chunks])
    embedded = [
        EmbeddedChunk(chunk=chunk, vector=vector)
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    index.delete_document(repo, source_doc)  # drop stale chunks before re-indexing
    index.upsert(embedded)
    return embedded
