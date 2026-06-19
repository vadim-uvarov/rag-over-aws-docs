"""Contract tests run against every VectorIndex implementation.

The in-memory index runs everywhere; LanceDB is included only where its wheel is
installed (skipped on platforms without one, e.g. Intel macOS).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

import pytest

from rag_aws.etl.indexing.memory_index import InMemoryVectorIndex
from rag_aws.etl.interfaces import Chunk, EmbeddedChunk, VectorIndex

IndexFactory = Callable[[Path], VectorIndex]


def _make_memory(_tmp: Path) -> VectorIndex:
    return InMemoryVectorIndex()


def _make_lancedb(tmp_path: Path) -> VectorIndex:
    from rag_aws.etl.indexing.lancedb_index import LanceDBIndex

    return LanceDBIndex(uri=str(tmp_path / "lancedb"), dimensions=3)


_FACTORIES = [pytest.param(_make_memory, id="memory")]
if importlib.util.find_spec("lancedb") is not None:
    _FACTORIES.append(pytest.param(_make_lancedb, id="lancedb"))


@pytest.fixture(params=_FACTORIES)
def index(request: pytest.FixtureRequest, tmp_path: Path) -> VectorIndex:
    factory: IndexFactory = request.param
    return factory(tmp_path)


def _embedded(chunk_id: str, vector: list[float], doc: str = "d.md") -> EmbeddedChunk:
    chunk = Chunk(
        chunk_id=chunk_id,
        text=f"text-{chunk_id}",
        source_doc=doc,
        repo="r",
        chunk_index=int(chunk_id[-1]) if chunk_id[-1].isdigit() else 0,
        char_start=0,
        char_end=1,
        token_count=1,
    )
    return EmbeddedChunk(chunk=chunk, vector=vector)


def test_upsert_then_count(index: VectorIndex) -> None:
    index.upsert([_embedded("a", [1.0, 0.0, 0.0]), _embedded("b", [0.0, 1.0, 0.0])])
    assert index.count() == 2


def test_search_returns_most_similar_first(index: VectorIndex) -> None:
    index.upsert([_embedded("near", [1.0, 0.0, 0.0]), _embedded("far", [0.0, 0.0, 1.0])])
    results = index.search([1.0, 0.0, 0.0], top_k=2)
    assert results[0].chunk_id == "near"


def test_upsert_is_idempotent_by_id(index: VectorIndex) -> None:
    index.upsert([_embedded("a", [1.0, 0.0, 0.0])])
    index.upsert([_embedded("a", [1.0, 0.0, 0.0])])
    assert index.count() == 1


def test_delete_document_removes_chunks(index: VectorIndex) -> None:
    index.upsert(
        [
            _embedded("a", [1.0, 0.0, 0.0], doc="keep.md"),
            _embedded("b", [0.0, 1.0, 0.0], doc="drop.md"),
        ]
    )
    index.delete_document("r", "drop.md")
    assert index.count() == 1


@pytest.mark.skipif(
    importlib.util.find_spec("lancedb") is None, reason="lancedb wheel not installed"
)
def test_lancedb_missing_table_raises_when_not_creating(tmp_path: Path) -> None:
    # Read-only consumers must fail fast instead of attempting a forbidden create.
    from rag_aws.etl.indexing.lancedb_index import LanceDBIndex, VectorStoreNotFoundError

    with pytest.raises(VectorStoreNotFoundError):
        LanceDBIndex(uri=str(tmp_path / "lancedb"), dimensions=3, create_if_missing=False)


@pytest.mark.skipif(
    importlib.util.find_spec("lancedb") is None, reason="lancedb wheel not installed"
)
def test_lancedb_opens_existing_table_when_not_creating(tmp_path: Path) -> None:
    from rag_aws.etl.indexing.lancedb_index import LanceDBIndex

    uri = str(tmp_path / "lancedb")
    LanceDBIndex(uri=uri, dimensions=3).upsert([_embedded("a", [1.0, 0.0, 0.0])])

    reopened = LanceDBIndex(uri=uri, dimensions=3, create_if_missing=False)
    assert reopened.count() == 1
