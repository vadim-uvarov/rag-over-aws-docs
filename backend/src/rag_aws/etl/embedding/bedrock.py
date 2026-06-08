"""Bedrock Titan Text Embeddings V2 embedder with retry/backoff.

Titan v2 embeds a single text per ``invoke_model`` call, so :meth:`embed_texts`
iterates, retrying throttled calls with exponential backoff. The Bedrock client
is injected (typed structurally) so tests can supply a fake.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from botocore.exceptions import ClientError

from rag_aws.config.settings import EMBEDDING_DIMENSIONS, TITAN_EMBED_MODEL_ID
from rag_aws.etl.interfaces import Embedder

# Bedrock error codes worth retrying.
_RETRYABLE_ERROR_CODES = frozenset({"ThrottlingException", "ModelTimeoutException"})


class InvokeModelClient(Protocol):
    """Minimal structural type for the part of the Bedrock client we use."""

    def invoke_model(self, *, modelId: str, body: str, accept: str, contentType: str) -> Any: ...  # noqa: N803


class BedrockTitanEmbedder(Embedder):
    """Embed text with Amazon Titan Text Embeddings V2 via Bedrock."""

    def __init__(
        self,
        client: InvokeModelClient,
        model_id: str = TITAN_EMBED_MODEL_ID,
        dimensions: int = EMBEDDING_DIMENSIONS,
        max_retries: int = 5,
        backoff_base_seconds: float = 0.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._model_id = model_id
        self._dimensions = dimensions
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._sleep = sleep

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        """Embed a single text, retrying retryable Bedrock errors with backoff."""
        request_body = json.dumps(
            {"inputText": text, "dimensions": self._dimensions, "normalize": True}
        )
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.invoke_model(
                    modelId=self._model_id,
                    body=request_body,
                    accept="application/json",
                    contentType="application/json",
                )
                payload = json.loads(response["body"].read())
                return list(payload["embedding"])
            except ClientError as error:
                code = error.response.get("Error", {}).get("Code", "")
                if code not in _RETRYABLE_ERROR_CODES or attempt == self._max_retries:
                    raise
                # Exponential backoff: base, 2x, 4x, ...
                self._sleep(self._backoff_base_seconds * (2**attempt))
        raise RuntimeError("unreachable: retry loop exited without returning")  # pragma: no cover
