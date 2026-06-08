"""Persist chunk text to the ``corpus/chunks/`` (B) prefix."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from rag_aws.config.settings import CHUNKS_PREFIX
from rag_aws.etl.interfaces import Chunk

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

_CHUNK_CONTENT_TYPE = "text/plain"


def chunk_key(repo: str, source_doc: str, chunk_index: int) -> str:
    """Build the S3 key for a chunk: ``corpus/chunks/<repo>/<doc>/<index>.txt``.

    The source document's extension is dropped so its chunks live in a folder
    named after the document.
    """
    doc_path = PurePosixPath(source_doc)
    doc_dir = doc_path.with_suffix("").as_posix()
    return f"{CHUNKS_PREFIX}{repo}/{doc_dir}/{chunk_index}.txt"


def write_chunks_to_s3(s3_client: S3Client, bucket: str, chunks: Sequence[Chunk]) -> list[str]:
    """Write each chunk's text to S3 (B) and return the keys written."""
    keys: list[str] = []
    for chunk in chunks:
        key = chunk_key(chunk.repo, chunk.source_doc, chunk.chunk_index)
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=chunk.text.encode("utf-8"),
            ContentType=_CHUNK_CONTENT_TYPE,
        )
        keys.append(key)
    return keys
