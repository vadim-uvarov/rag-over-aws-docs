"""Process one document event: index on create/update, delete on remove.

This is the body of the Step Functions Map state — it runs once per item in the
batch. The core :func:`process_item` takes injected dependencies so it is fully
testable; :func:`handler` builds the real Bedrock/LanceDB dependencies.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

import boto3

from rag_aws.config.settings import VECTOR_STORE_PREFIX, load_settings
from rag_aws.etl.chunking.chunker import NaiveChunker
from rag_aws.etl.chunking.storage import delete_document_chunks
from rag_aws.etl.embedding.bedrock import BedrockTitanEmbedder, InvokeModelClient
from rag_aws.etl.handlers.events import ACTION_REMOVED
from rag_aws.etl.indexing.lancedb_index import LanceDBIndex
from rag_aws.etl.interfaces import Chunker, Embedder, VectorIndex
from rag_aws.etl.pipeline import process_document
from rag_aws.ingestion.keys import parse_raw_key

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

BUCKET_ENV = "PROJECT_BUCKET_NAME"


def process_item(
    item: dict[str, str],
    *,
    s3_client: S3Client,
    chunker: Chunker,
    embedder: Embedder,
    index: VectorIndex,
) -> dict[str, Any]:
    """Index a created/updated document, or delete a removed one.

    Args:
        item: ``{"bucket", "key", "action"}`` from the dispatcher.
        s3_client: S3 client.
        chunker: Chunking implementation.
        embedder: Embedding implementation.
        index: Vector index implementation.

    Returns:
        A small result dict describing what happened (for SFN output / logging).
    """
    bucket, key, action = item["bucket"], item["key"], item["action"]
    repo, source_doc = parse_raw_key(key)

    if action == ACTION_REMOVED:
        index.delete_document(repo, source_doc)
        deleted_chunks = delete_document_chunks(s3_client, bucket, repo, source_doc)
        return {"key": key, "action": "deleted", "chunks": deleted_chunks}

    raw = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
    embedded = process_document(
        raw.decode("utf-8"),
        source_doc=source_doc,
        repo=repo,
        chunker=chunker,
        embedder=embedder,
        index=index,
        s3_client=s3_client,
        bucket=bucket,
    )
    return {"key": key, "action": "indexed", "chunks": len(embedded)}


def handler(event: dict[str, str], _context: object = None) -> dict[str, Any]:
    """Lambda entry point: process a single document event with real backends."""
    settings = load_settings()
    bucket = os.environ.get(BUCKET_ENV, settings.bucket_name)

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    bedrock_client = cast(
        InvokeModelClient, boto3.client("bedrock-runtime", region_name=settings.aws_region)
    )
    embedder = BedrockTitanEmbedder(bedrock_client, model_id=settings.embed_model_id)
    index = LanceDBIndex(
        uri=f"s3://{bucket}/{VECTOR_STORE_PREFIX}", dimensions=settings.embedding_dimensions
    )
    return process_item(
        event, s3_client=s3_client, chunker=NaiveChunker(), embedder=embedder, index=index
    )
