"""In-memory vector index: a dependency-free reference implementation.

Used for unit/contract tests and small local pipelines (no native deps, runs
everywhere). Computes cosine similarity in pure Python.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from rag_aws.etl.interfaces import EmbeddedChunk, SearchResult, VectorIndex


class InMemoryVectorIndex(VectorIndex):
    """A dict-backed :class:`VectorIndex` keyed by ``chunk_id``."""

    def __init__(self) -> None:
        self._store: dict[str, EmbeddedChunk] = {}

    def upsert(self, embedded_chunks: Sequence[EmbeddedChunk]) -> None:
        for embedded in embedded_chunks:
            self._store[embedded.chunk.chunk_id] = embedded

    def delete_document(self, repo: str, source_doc: str) -> None:
        to_remove = [
            chunk_id
            for chunk_id, embedded in self._store.items()
            if embedded.chunk.repo == repo and embedded.chunk.source_doc == source_doc
        ]
        for chunk_id in to_remove:
            del self._store[chunk_id]

    def search(self, query_vector: Sequence[float], top_k: int) -> list[SearchResult]:
        scored = [
            (_cosine_similarity(query_vector, embedded.vector), embedded)
            for embedded in self._store.values()
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [_to_result(score, embedded) for score, embedded in scored[:top_k]]

    def count(self) -> int:
        return len(self._store)


def _to_result(score: float, embedded: EmbeddedChunk) -> SearchResult:
    chunk = embedded.chunk
    return SearchResult(
        chunk_id=chunk.chunk_id,
        text=chunk.text,
        source_doc=chunk.source_doc,
        repo=chunk.repo,
        chunk_index=chunk.chunk_index,
        score=score,
    )


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
