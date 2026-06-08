"""Contract tests for Embedder implementations.

Only the fake embedder runs here; the real Bedrock embedder needs AWS and is
covered by mocked unit tests in ``tests/unit/test_bedrock_embedder.py``.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from rag_aws.etl.embedding.fake import FakeEmbedder
from rag_aws.etl.interfaces import Embedder

EmbedderFactory = Callable[[], Embedder]

_FACTORIES = [pytest.param(lambda: FakeEmbedder(dimensions=8), id="fake")]


@pytest.fixture(params=_FACTORIES)
def embedder(request: pytest.FixtureRequest) -> Embedder:
    factory: EmbedderFactory = request.param
    return factory()


def test_returns_one_vector_per_input(embedder: Embedder) -> None:
    vectors = embedder.embed_texts(["a", "b", "c"])
    assert len(vectors) == 3


def test_vector_matches_declared_dimensions(embedder: Embedder) -> None:
    [vector] = embedder.embed_texts(["only"])
    assert len(vector) == embedder.dimensions


def test_is_deterministic(embedder: Embedder) -> None:
    assert embedder.embed_texts(["repeat"]) == embedder.embed_texts(["repeat"])


def test_empty_input(embedder: Embedder) -> None:
    assert embedder.embed_texts([]) == []
