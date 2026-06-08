"""Deterministic in-memory embedder for tests and local pipelines."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence

from rag_aws.config.settings import EMBEDDING_DIMENSIONS
from rag_aws.etl.interfaces import Embedder


class FakeEmbedder(Embedder):
    """Map text to a deterministic unit vector, no network required.

    Identical text always yields the same vector, and vectors are L2-normalised
    so cosine similarity behaves like a real embedder's.
    """

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS) -> None:
        self._dimensions = dimensions

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        # Seed a per-dimension pseudo-random value from a hash of the text.
        values: list[float] = []
        for index in range(self._dimensions):
            digest = hashlib.sha256(f"{index}:{text}".encode()).digest()
            values.append(int.from_bytes(digest[:8], "big") / 2**64 - 0.5)
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
