"""API Lambda: synchronous ``/ask`` endpoint returning an answer + ranked chunks.

The core (:func:`process_query`) is pure orchestration over injected
dependencies so it is fully testable; :func:`handler` parses the API Gateway
event, builds the real backends, and maps the result to an HTTP response.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast
from uuid import uuid4

import boto3
from botocore.config import Config

from rag_aws.config.settings import VECTOR_STORE_PREFIX, load_settings
from rag_aws.etl.embedding.bedrock import BedrockTitanEmbedder, InvokeModelClient
from rag_aws.etl.indexing.lancedb_index import LanceDBIndex
from rag_aws.etl.interfaces import SearchResult
from rag_aws.observability import get_logger
from rag_aws.query.generator import AnswerGenerator, NovaMicroModel
from rag_aws.query.links import build_doc_link
from rag_aws.query.retriever import Retriever
from rag_aws.query.session import SessionQuota, SessionUsage
from rag_aws.query.tracing import LangfuseKeys, load_langfuse_keys, record_query_trace

_logger = get_logger(__name__)

SESSION_TABLE_ENV = "SESSION_TABLE_NAME"
LANGFUSE_SECRET_ENV = "LANGFUSE_SECRET_NAME"
BUCKET_ENV = "PROJECT_BUCKET_NAME"

# Bound AWS client connect/read time and retries so a stuck downstream call fails
# fast with a clear error instead of riding to the Lambda's 30s timeout (which the
# caller sees as an opaque 504). Read timeout stays under the API Gateway 29s limit.
_CONNECT_TIMEOUT_SECONDS = 3
_READ_TIMEOUT_SECONDS = 20
_MAX_ATTEMPTS = 2


class QuotaRecorder(Protocol):
    """Records a question against a session and reports usage."""

    def record_question(self, session_id: str, now: float | None = None) -> SessionUsage: ...


@dataclass
class QueryDependencies:
    """Everything :func:`process_query` needs, injected for testability."""

    retriever: Retriever
    generator: AnswerGenerator
    quota: QuotaRecorder
    langfuse_keys: LangfuseKeys | None = None


def shape_chunks(hits: Sequence[SearchResult]) -> list[dict[str, Any]]:
    """Render hits (already ordered by descending relevance) for the response."""
    return [
        {
            "source_doc": hit.source_doc,
            "link": build_doc_link(hit.repo, hit.source_doc),
            "cosine_distance": round(1.0 - hit.score, 6),
        }
        for hit in hits
    ]


def _session_view(usage: SessionUsage) -> dict[str, Any]:
    return {"id": usage.session_id, "used": usage.used, "limit": usage.limit}


def build_aws_client_config() -> Config:
    """Return a botocore config that fails fast instead of riding to the Lambda timeout."""
    return Config(
        connect_timeout=_CONNECT_TIMEOUT_SECONDS,
        read_timeout=_READ_TIMEOUT_SECONDS,
        retries={"max_attempts": _MAX_ATTEMPTS},
    )


def process_query(body: dict[str, Any], deps: QueryDependencies) -> tuple[int, dict[str, Any]]:
    """Run one query end-to-end; return an ``(http_status, payload)`` pair.

    Each downstream stage is logged so a timeout (which produces no traceback)
    can be localised to the exact call that hung.
    """
    question = str(body.get("question") or "").strip()
    if not question:
        return 400, {"error": "'question' is required"}

    session_id = str(body.get("session_id") or "").strip() or uuid4().hex

    _logger.info("recording session quota", extra={"session_id": session_id})
    usage = deps.quota.record_question(session_id)
    if not usage.allowed:
        return 429, {"error": "session question limit reached", "session": _session_view(usage)}

    _logger.info("retrieving chunks", extra={"session_id": session_id})
    hits = deps.retriever.retrieve(question)

    _logger.info("generating answer", extra={"session_id": session_id, "chunks": len(hits)})
    answer = deps.generator.generate_answer(question, hits)

    _logger.info("recording trace", extra={"session_id": session_id})
    record_query_trace(deps.langfuse_keys, question=question, chunks=hits, answer=answer)

    return 200, {
        "answer": answer,
        "chunks": shape_chunks(hits),
        "session": _session_view(usage),
    }


def _http_response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(payload),
    }


def handler(event: dict[str, Any], _context: object = None) -> dict[str, Any]:
    """Lambda entry point for API Gateway proxy integration."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _http_response(400, {"error": "request body must be valid JSON"})

    _logger.info("building dependencies")
    deps = _build_dependencies()
    _logger.info("dependencies built")

    status, payload = process_query(body, deps)
    _logger.info("handled /ask", extra={"status": status, "chunks": len(payload.get("chunks", []))})
    return _http_response(status, payload)


def _build_dependencies() -> QueryDependencies:
    """Construct the real Bedrock / LanceDB / DynamoDB / Secrets backends."""
    settings = load_settings()
    bucket = os.environ.get(BUCKET_ENV, settings.bucket_name)
    region = settings.aws_region
    client_config = build_aws_client_config()

    bedrock_client = cast(
        "InvokeModelClient",
        boto3.client("bedrock-runtime", region_name=region, config=client_config),
    )
    embedder = BedrockTitanEmbedder(bedrock_client, model_id=settings.embed_model_id)

    # Connecting LanceDB reads the vector store from S3; log around it because this
    # cold S3 access is a prime hang suspect and the object-store layer is silent.
    vector_store_uri = f"s3://{bucket}/{VECTOR_STORE_PREFIX}"
    _logger.info("connecting vector index", extra={"uri": vector_store_uri})
    index = LanceDBIndex(uri=vector_store_uri, dimensions=settings.embedding_dimensions)
    _logger.info("vector index connected")
    retriever = Retriever(embedder, index, settings=settings)

    generator = AnswerGenerator(
        NovaMicroModel(
            model_id=settings.generation_model_id, region_name=region, config=client_config
        )
    )

    quota = SessionQuota(
        boto3.client("dynamodb", region_name=region, config=client_config),
        table_name=os.environ[SESSION_TABLE_ENV],
        limit=settings.session_question_limit,
        ttl_hours=settings.session_ttl_hours,
    )

    langfuse_keys = None
    secret_name = os.environ.get(LANGFUSE_SECRET_ENV)
    if secret_name:
        langfuse_keys = load_langfuse_keys(
            boto3.client("secretsmanager", region_name=region, config=client_config), secret_name
        )

    return QueryDependencies(
        retriever=retriever, generator=generator, quota=quota, langfuse_keys=langfuse_keys
    )
