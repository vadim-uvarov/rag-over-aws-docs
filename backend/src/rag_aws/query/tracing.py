"""Optional Langfuse Cloud tracing for RAG queries.

Keys live in Secrets Manager. Tracing is best-effort: if keys are missing or the
Langfuse call fails, querying still succeeds.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError

from rag_aws.etl.interfaces import SearchResult

if TYPE_CHECKING:
    from mypy_boto3_secretsmanager import SecretsManagerClient

DEFAULT_HOST = "https://cloud.langfuse.com"


@dataclass(frozen=True)
class LangfuseKeys:
    """Credentials for Langfuse Cloud."""

    public_key: str
    secret_key: str
    host: str = DEFAULT_HOST


def load_langfuse_keys(
    secrets_client: SecretsManagerClient, secret_name: str
) -> LangfuseKeys | None:
    """Load Langfuse keys from Secrets Manager, or ``None`` if unavailable/incomplete."""
    try:
        response = secrets_client.get_secret_value(SecretId=secret_name)
    except ClientError:
        return None
    raw = response.get("SecretString")
    if not raw:
        return None
    data = json.loads(raw)
    public_key, secret_key = data.get("public_key"), data.get("secret_key")
    if not public_key or not secret_key:
        return None
    return LangfuseKeys(
        public_key=public_key, secret_key=secret_key, host=data.get("host", DEFAULT_HOST)
    )


def record_query_trace(
    keys: LangfuseKeys | None,
    *,
    question: str,
    chunks: Sequence[SearchResult],
    answer: str,
) -> bool:
    """Send a trace to Langfuse if configured; return whether a trace was sent.

    Never raises — tracing failures must not break a query.
    """
    if keys is None:
        return False
    try:
        from langfuse import Langfuse

        client = Langfuse(public_key=keys.public_key, secret_key=keys.secret_key, host=keys.host)
        client.create_event(
            name="rag-query",
            input={"question": question},
            output={"answer": answer},
            metadata={"retrieved_chunk_ids": [chunk.chunk_id for chunk in chunks]},
        )
        client.flush()
    except Exception:  # tracing is strictly best-effort; never break a query
        return False
    return True
