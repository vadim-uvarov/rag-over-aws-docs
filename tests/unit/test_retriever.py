"""Unit tests for retrieval filtering and the Retriever."""

from __future__ import annotations

from collections.abc import Sequence

from rag_aws.config.settings import Settings
from rag_aws.etl.interfaces import Embedder, SearchResult, VectorIndex
from rag_aws.query.retriever import Retriever, filter_hits


def _hit(chunk_id: str, score: float) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id, text=chunk_id, source_doc="d.md", repo="r", chunk_index=0, score=score
    )


def test_filter_keeps_hits_at_or_above_threshold() -> None:
    hits = [_hit("a", 0.9), _hit("b", 0.7), _hit("c", 0.69)]
    kept = filter_hits(hits, similarity_threshold=0.7, top_k_final=5)
    # Exactly 0.7 is kept (inclusive); 0.69 is dropped.
    assert [hit.chunk_id for hit in kept] == ["a", "b"]


def test_filter_truncates_to_top_k() -> None:
    hits = [_hit(str(i), 0.95) for i in range(10)]
    assert len(filter_hits(hits, similarity_threshold=0.7, top_k_final=5)) == 5


def test_filter_returns_empty_when_no_survivors() -> None:
    hits = [_hit("a", 0.5), _hit("b", 0.1)]
    assert filter_hits(hits, similarity_threshold=0.7, top_k_final=5) == []


class _StubEmbedder(Embedder):
    @property
    def dimensions(self) -> int:
        return 3

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


class _StubIndex(VectorIndex):
    def __init__(self, hits: list[SearchResult]) -> None:
        self._hits = hits
        self.requested_top_k: int | None = None

    def upsert(self, embedded_chunks: object) -> None: ...
    def delete_document(self, repo: str, source_doc: str) -> None: ...
    def count(self) -> int:
        return len(self._hits)

    def search(self, query_vector: Sequence[float], top_k: int) -> list[SearchResult]:
        self.requested_top_k = top_k
        return self._hits


def test_retriever_uses_initial_k_and_filters() -> None:
    index = _StubIndex([_hit("a", 0.95), _hit("b", 0.72), _hit("c", 0.3)])
    settings = Settings(
        retrieval_top_k_initial=20, retrieval_similarity_threshold=0.7, retrieval_top_k_final=5
    )
    retriever = Retriever(_StubEmbedder(), index, settings=settings)

    kept = retriever.retrieve("what is s3?")
    assert [hit.chunk_id for hit in kept] == ["a", "b"]
    assert index.requested_top_k == 20
