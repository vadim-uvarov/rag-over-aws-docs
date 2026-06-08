"""Unit tests for the naive chunker (using a fake word-based token counter)."""

from __future__ import annotations

from rag_aws.etl.chunking.chunker import NaiveChunker
from rag_aws.etl.interfaces import TokenCounter


class WordCounter(TokenCounter):
    """Counts whitespace-separated words — deterministic and offline."""

    def count_tokens(self, text: str) -> int:
        return len(text.split())


def _chunker(chunk_size: int = 10, overlap: int = 2) -> NaiveChunker:
    return NaiveChunker(
        token_counter=WordCounter(), chunk_size_tokens=chunk_size, chunk_overlap_tokens=overlap
    )


def test_empty_or_whitespace_document_yields_no_chunks() -> None:
    assert _chunker().chunk_document("", source_doc="d.md", repo="r") == []
    assert _chunker().chunk_document("   \n  ", source_doc="d.md", repo="r") == []


def test_tiny_document_is_one_chunk() -> None:
    chunks = _chunker().chunk_document("a short doc", source_doc="d.md", repo="r")
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "r/d.md#0"
    assert chunks[0].chunk_index == 0


def test_large_document_splits_into_multiple_chunks() -> None:
    text = " ".join(f"word{i}" for i in range(100))
    chunks = _chunker(chunk_size=10, overlap=0).chunk_document(text, source_doc="d.md", repo="r")
    assert len(chunks) > 1
    # Each chunk respects the token budget measured by the injected counter.
    assert all(chunk.token_count <= 10 for chunk in chunks)


def test_chunk_metadata_is_populated() -> None:
    text = " ".join(f"word{i}" for i in range(60))
    chunks = _chunker().chunk_document(text, source_doc="guide/intro.md", repo="repo-x")
    for index, chunk in enumerate(chunks):
        assert chunk.repo == "repo-x"
        assert chunk.source_doc == "guide/intro.md"
        assert chunk.chunk_index == index
        assert chunk.token_count > 0
        assert 0 <= chunk.char_start <= chunk.char_end <= len(text)
