"""Unit tests for the in-memory vector index."""

from __future__ import annotations

from rag_aws.etl.indexing.memory_index import InMemoryVectorIndex
from rag_aws.etl.interfaces import Chunk, EmbeddedChunk


def _embedded(
    chunk_id: str, vector: list[float], repo: str = "r", doc: str = "d.md"
) -> EmbeddedChunk:
    chunk = Chunk(
        chunk_id=chunk_id,
        text=f"text-{chunk_id}",
        source_doc=doc,
        repo=repo,
        chunk_index=0,
        char_start=0,
        char_end=1,
        token_count=1,
    )
    return EmbeddedChunk(chunk=chunk, vector=vector)


def test_upsert_and_count() -> None:
    index = InMemoryVectorIndex()
    index.upsert([_embedded("a", [1.0, 0.0]), _embedded("b", [0.0, 1.0])])
    assert index.count() == 2


def test_upsert_same_id_replaces() -> None:
    index = InMemoryVectorIndex()
    index.upsert([_embedded("a", [1.0, 0.0])])
    index.upsert([_embedded("a", [0.0, 1.0])])
    assert index.count() == 1


def test_search_orders_by_similarity() -> None:
    index = InMemoryVectorIndex()
    index.upsert([_embedded("near", [1.0, 0.0]), _embedded("far", [0.0, 1.0])])
    results = index.search([1.0, 0.0], top_k=2)
    assert [r.chunk_id for r in results] == ["near", "far"]
    assert results[0].score > results[1].score


def test_search_respects_top_k() -> None:
    index = InMemoryVectorIndex()
    index.upsert([_embedded(str(i), [float(i), 1.0]) for i in range(5)])
    assert len(index.search([1.0, 1.0], top_k=3)) == 3


def test_delete_document_removes_its_chunks() -> None:
    index = InMemoryVectorIndex()
    index.upsert(
        [
            _embedded("a", [1.0, 0.0], doc="keep.md"),
            _embedded("b", [0.0, 1.0], doc="drop.md"),
        ]
    )
    index.delete_document("r", "drop.md")
    assert index.count() == 1
    assert index.search([0.0, 1.0], top_k=1)[0].chunk_id == "a"


def test_search_empty_index_returns_nothing() -> None:
    assert InMemoryVectorIndex().search([1.0, 0.0], top_k=5) == []
