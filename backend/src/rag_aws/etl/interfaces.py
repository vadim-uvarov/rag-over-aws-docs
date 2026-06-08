"""Contracts for the ETL stages and the data that flows between them.

The stages — chunk, embed, index — are defined as abstract base classes so
implementations can be swapped freely (a real Bedrock embedder vs. a fake one
in tests, LanceDB vs. an in-memory index, etc.). Each ABC has a single, narrow
responsibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chunk:
    """A unit of document text produced by a :class:`Chunker`.

    Attributes:
        chunk_id: Stable identifier, ``<repo>/<source_doc>#<chunk_index>``.
        text: The chunk's text.
        source_doc: Repo-relative path of the source document.
        repo: Logical source repo name.
        chunk_index: Zero-based position of this chunk within the document.
        char_start: Best-effort start offset of the chunk in the source text.
        char_end: Best-effort end offset (exclusive) of the chunk in the source.
        token_count: Token count per the chunker's :class:`TokenCounter`.
    """

    chunk_id: str
    text: str
    source_doc: str
    repo: str
    chunk_index: int
    char_start: int
    char_end: int
    token_count: int

    @staticmethod
    def make_id(repo: str, source_doc: str, chunk_index: int) -> str:
        """Build the stable chunk id from its provenance."""
        return f"{repo}/{source_doc}#{chunk_index}"


@dataclass(frozen=True)
class EmbeddedChunk:
    """A chunk paired with its embedding vector."""

    chunk: Chunk
    vector: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class SearchResult:
    """A vector-store hit: chunk provenance plus a cosine similarity score."""

    chunk_id: str
    text: str
    source_doc: str
    repo: str
    chunk_index: int
    score: float  # cosine similarity in [-1, 1]; higher is more similar


class TokenCounter(ABC):
    """Counts tokens in text, used for chunk-size budgeting."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Return the number of tokens in ``text``."""


class Chunker(ABC):
    """Splits a document into :class:`Chunk` objects."""

    @abstractmethod
    def chunk_document(self, text: str, *, source_doc: str, repo: str) -> list[Chunk]:
        """Split ``text`` into chunks, attaching provenance metadata."""


class Embedder(ABC):
    """Embeds text into fixed-dimension vectors."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensionality of the produced vectors."""

    @abstractmethod
    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed each input text, returning one vector per input (order-preserving)."""


class VectorIndex(ABC):
    """Stores embedded chunks and answers nearest-neighbour queries."""

    @abstractmethod
    def upsert(self, embedded_chunks: Sequence[EmbeddedChunk]) -> None:
        """Insert or replace embedded chunks (idempotent by ``chunk_id``)."""

    @abstractmethod
    def delete_document(self, repo: str, source_doc: str) -> None:
        """Remove every chunk belonging to one source document."""

    @abstractmethod
    def search(self, query_vector: Sequence[float], top_k: int) -> list[SearchResult]:
        """Return up to ``top_k`` hits ordered by descending cosine similarity."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of stored chunks."""
