"""Retrieval: embed the query, search, filter by similarity, keep top-k.

Strategy (see plan §"Challenges"): fetch top-20 → keep cosine similarity ≥ 0.7
(equivalently cosine distance ≤ 0.3) → keep top-5 → if empty, the generator
returns the fallback answer.
"""

from __future__ import annotations

from collections.abc import Sequence

from rag_aws.config.settings import Settings, load_settings
from rag_aws.etl.interfaces import Embedder, SearchResult, VectorIndex


def filter_hits(
    hits: Sequence[SearchResult], similarity_threshold: float, top_k_final: int
) -> list[SearchResult]:
    """Keep hits scoring at least ``similarity_threshold``, then the top ``top_k_final``.

    Hits are assumed already sorted by descending similarity (as the vector index
    returns them). The threshold is inclusive (a hit at exactly the threshold is
    kept).
    """
    kept = [hit for hit in hits if hit.score >= similarity_threshold]
    return kept[:top_k_final]


class Retriever:
    """Embeds a question and returns the most relevant chunks."""

    def __init__(
        self,
        embedder: Embedder,
        index: VectorIndex,
        settings: Settings | None = None,
    ) -> None:
        self._embedder = embedder
        self._index = index
        self._settings = settings or load_settings()

    def retrieve(self, question: str) -> list[SearchResult]:
        """Return up to ``top_k_final`` chunks with similarity ≥ threshold (may be empty)."""
        query_vector = self._embedder.embed_texts([question])[0]
        hits = self._index.search(query_vector, self._settings.retrieval_top_k_initial)
        return filter_hits(
            hits,
            self._settings.retrieval_similarity_threshold,
            self._settings.retrieval_top_k_final,
        )
