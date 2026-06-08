"""Unit tests for the Bedrock Titan embedder (with a fake invoke_model client)."""

from __future__ import annotations

import json
from typing import Any

import pytest
from botocore.exceptions import ClientError

from rag_aws.etl.embedding.bedrock import BedrockTitanEmbedder


class _Body:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw


def _ok(vector: list[float]) -> dict[str, Any]:
    return {"body": _Body({"embedding": vector})}


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, "InvokeModel")


class FakeClient:
    """Returns queued behaviours per call; raises queued exceptions."""

    def __init__(self, behaviours: list[Any]) -> None:
        self._behaviours = behaviours
        self.calls = 0

    def invoke_model(self, **_kwargs: Any) -> Any:
        behaviour = self._behaviours[self.calls]
        self.calls += 1
        if isinstance(behaviour, Exception):
            raise behaviour
        return behaviour


def test_embeds_text_to_returned_vector() -> None:
    client = FakeClient([_ok([0.1, 0.2, 0.3])])
    embedder = BedrockTitanEmbedder(client, dimensions=3)
    assert embedder.embed_texts(["hello"]) == [[0.1, 0.2, 0.3]]


def test_dimensions_property() -> None:
    assert BedrockTitanEmbedder(FakeClient([]), dimensions=512).dimensions == 512


def test_retries_throttling_then_succeeds() -> None:
    sleeps: list[float] = []
    client = FakeClient([_client_error("ThrottlingException"), _ok([1.0])])
    embedder = BedrockTitanEmbedder(
        client, dimensions=1, backoff_base_seconds=0.01, sleep=sleeps.append
    )
    assert embedder.embed_texts(["x"]) == [[1.0]]
    assert client.calls == 2
    assert len(sleeps) == 1  # one backoff before the successful retry


def test_non_retryable_error_raises_immediately() -> None:
    client = FakeClient([_client_error("ValidationException"), _ok([1.0])])
    embedder = BedrockTitanEmbedder(client, dimensions=1)
    with pytest.raises(ClientError):
        embedder.embed_texts(["x"])
    assert client.calls == 1  # not retried


def test_exhausting_retries_raises() -> None:
    client = FakeClient([_client_error("ThrottlingException")] * 3)
    embedder = BedrockTitanEmbedder(
        client, dimensions=1, max_retries=2, backoff_base_seconds=0.0, sleep=lambda _s: None
    )
    with pytest.raises(ClientError):
        embedder.embed_texts(["x"])
    assert client.calls == 3  # initial + 2 retries
