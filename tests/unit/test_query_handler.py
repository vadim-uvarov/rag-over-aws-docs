"""Unit tests for the query handler core (process_query) with fakes."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import pytest

from rag_aws.etl.indexing.lancedb_index import VectorStoreNotFoundError
from rag_aws.etl.interfaces import Embedder, SearchResult, VectorIndex
from rag_aws.query import handler as handler_module
from rag_aws.query.generator import FALLBACK_ANSWER, AnswerGenerator
from rag_aws.query.handler import (
    QueryDependencies,
    build_aws_client_config,
    handler,
    process_query,
    shape_chunks,
)
from rag_aws.query.retriever import Retriever
from rag_aws.query.session import SessionUsage


def _hit(chunk_id: str, score: float, source_doc: str = "s3/intro.md") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        text=f"text-{chunk_id}",
        source_doc=source_doc,
        repo="amazon-s3-userguide",
        chunk_index=0,
        score=score,
    )


class _StubEmbedder(Embedder):
    @property
    def dimensions(self) -> int:
        return 3

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class _StubIndex(VectorIndex):
    def __init__(self, hits: list[SearchResult]) -> None:
        self._hits = hits

    def upsert(self, embedded_chunks: object) -> None: ...
    def delete_document(self, repo: str, source_doc: str) -> None: ...
    def count(self) -> int:
        return len(self._hits)

    def search(self, query_vector: Sequence[float], top_k: int) -> list[SearchResult]:
        return self._hits


class _EchoModel:
    def invoke(self, prompt: str) -> str:
        return "the answer"


class _FakeQuota:
    def __init__(self, *, used: int, limit: int, allowed: bool) -> None:
        self._usage = SessionUsage("sess", used, limit, allowed)

    def record_question(self, session_id: str, now: float | None = None) -> SessionUsage:
        return SessionUsage(session_id, self._usage.used, self._usage.limit, self._usage.allowed)


def _deps(hits: list[SearchResult], *, allowed: bool = True) -> QueryDependencies:
    return QueryDependencies(
        retriever=Retriever(_StubEmbedder(), _StubIndex(hits)),
        generator=AnswerGenerator(_EchoModel()),
        quota=_FakeQuota(used=1, limit=20, allowed=allowed),
    )


def test_missing_question_returns_400() -> None:
    status, payload = process_query({}, _deps([]))
    assert status == 400
    assert "question" in payload["error"]


def test_over_quota_returns_429() -> None:
    status, payload = process_query({"question": "hi"}, _deps([], allowed=False))
    assert status == 429
    assert payload["session"]["limit"] == 20


def test_happy_path_returns_answer_and_ranked_chunks() -> None:
    hits = [_hit("a", 0.95), _hit("b", 0.8)]
    status, payload = process_query({"question": "what is s3?", "session_id": "s1"}, _deps(hits))
    assert status == 200
    assert payload["answer"] == "the answer"
    assert [chunk["cosine_distance"] for chunk in payload["chunks"]] == [
        round(1 - 0.95, 6),
        round(1 - 0.8, 6),
    ]
    assert payload["session"]["id"] == "s1"


def test_no_relevant_chunks_yields_fallback() -> None:
    # All hits below threshold → retriever returns nothing → fallback answer.
    status, payload = process_query({"question": "nonsense"}, _deps([_hit("x", 0.1)]))
    assert status == 200
    assert payload["answer"] == FALLBACK_ANSWER
    assert payload["chunks"] == []


def test_shape_chunks_builds_links_and_distance() -> None:
    [chunk] = shape_chunks([_hit("a", 0.75)])
    assert chunk["source_doc"] == "s3/intro.md"
    assert chunk["link"].startswith("https://github.com/awsdocs/amazon-s3-userguide/")
    assert chunk["cosine_distance"] == round(1 - 0.75, 6)


def test_aws_client_config_bounds_timeouts_and_retries() -> None:
    # Fast-fail config keeps a stuck AWS call under the API Gateway 29s limit.
    # botocore sets these attributes dynamically (untyped), so read via Any.
    config: Any = build_aws_client_config()
    assert config.connect_timeout == 3
    assert config.read_timeout == 20
    assert config.retries == {"max_attempts": 2}


def test_handler_returns_503_when_vector_store_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A missing vector store must fail fast as 503, not hang attempting a write.
    def _raise() -> QueryDependencies:
        raise VectorStoreNotFoundError("not built")

    monkeypatch.setattr(handler_module, "_build_dependencies", _raise)
    response = handler({"body": json.dumps({"question": "hi"})})

    assert response["statusCode"] == 503
    assert "not ready" in json.loads(response["body"])["error"]
