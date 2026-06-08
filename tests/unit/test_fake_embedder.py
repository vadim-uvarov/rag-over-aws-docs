"""Unit tests for the deterministic fake embedder."""

from __future__ import annotations

import math

from rag_aws.etl.embedding.fake import FakeEmbedder


def test_returns_one_vector_per_text_of_right_dimension() -> None:
    embedder = FakeEmbedder(dimensions=16)
    vectors = embedder.embed_texts(["a", "b", "c"])
    assert len(vectors) == 3
    assert all(len(vector) == 16 for vector in vectors)


def test_is_deterministic() -> None:
    embedder = FakeEmbedder(dimensions=8)
    assert embedder.embed_texts(["hello"]) == embedder.embed_texts(["hello"])


def test_distinct_texts_produce_distinct_vectors() -> None:
    embedder = FakeEmbedder(dimensions=8)
    [a], [b] = embedder.embed_texts(["hello"]), embedder.embed_texts(["world"])
    assert a != b


def test_vectors_are_unit_normalised() -> None:
    [vector] = FakeEmbedder(dimensions=32).embed_texts(["something"])
    assert math.isclose(math.sqrt(sum(v * v for v in vector)), 1.0, rel_tol=1e-9)


def test_empty_input_returns_empty_list() -> None:
    assert FakeEmbedder().embed_texts([]) == []
