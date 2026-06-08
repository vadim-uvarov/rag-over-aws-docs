"""Central settings for the backend.

Holds the AWS region, the project S3 bucket name, the Bedrock model
identifiers, the single-bucket prefix layout, and the retrieval / session
parameters shared across the backend. Values default to the project's
locked-in choices (see ``.claude/initial-plan.md``) and can be overridden via
environment variables, which keeps tests hermetic and supports per-environment
deploys.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

# Bedrock model identifiers (cheapest options for the demo; see plan Decisions Log).
TITAN_EMBED_MODEL_ID = "amazon.titan-embed-text-v2:0"
NOVA_MICRO_MODEL_ID = "amazon.nova-micro-v1:0"
EMBEDDING_DIMENSIONS = 512  # 512-dim Titan v2 output, chosen for cost/storage

# Single project bucket: prefix layout (keep in sync with docs/architecture.md).
RAW_PREFIX = "corpus/raw/"  # (A) raw AWS markdown, key = <repo>/<path>.md
CHUNKS_PREFIX = "corpus/chunks/"  # (B) plain-text chunks
VECTOR_STORE_PREFIX = "corpus/vector-store/"  # (C) LanceDB table(s)
MANIFESTS_PREFIX = "corpus/manifests/"  # (D) ingestion state / content hashes
WEB_PREFIX = "web/"  # frontend build artifacts (CloudFront origin)


def _read_int(env: Mapping[str, str], key: str, default: int) -> int:
    """Read an int from ``env`` under ``key``, raising a clear error on bad input."""
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"Environment variable {key}={raw!r} is not a valid integer") from error


def _read_float(env: Mapping[str, str], key: str, default: float) -> float:
    """Read a float from ``env`` under ``key``, raising a clear error on bad input."""
    raw = env.get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as error:
        raise ValueError(f"Environment variable {key}={raw!r} is not a valid number") from error


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the backend.

    Attributes:
        aws_region: AWS region for all clients and resources.
        bucket_name: Name of the single project S3 bucket (empty until deployed).
        embed_model_id: Bedrock model id for query/document embeddings.
        generation_model_id: Bedrock model id for answer generation.
        embedding_dimensions: Dimensionality of the embedding vectors.
        retrieval_top_k_initial: Vectors fetched from the store before filtering.
        retrieval_similarity_threshold: Minimum cosine similarity to keep a chunk.
        retrieval_top_k_final: Chunks kept after filtering, passed to generation.
        session_question_limit: Max questions allowed per session.
        session_ttl_hours: Lifetime of a session's quota counter.
    """

    aws_region: str = "eu-west-1"
    bucket_name: str = ""
    embed_model_id: str = TITAN_EMBED_MODEL_ID
    generation_model_id: str = NOVA_MICRO_MODEL_ID
    embedding_dimensions: int = EMBEDDING_DIMENSIONS
    retrieval_top_k_initial: int = 20
    retrieval_similarity_threshold: float = 0.7
    retrieval_top_k_final: int = 5
    session_question_limit: int = 20
    session_ttl_hours: int = 24


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build a :class:`Settings` from environment variables, falling back to defaults.

    Args:
        env: Mapping to read overrides from. Defaults to ``os.environ``.

    Returns:
        A populated, immutable :class:`Settings`.
    """
    source = os.environ if env is None else env
    defaults = Settings()
    return Settings(
        aws_region=source.get("AWS_REGION", defaults.aws_region),
        bucket_name=source.get("PROJECT_BUCKET_NAME", defaults.bucket_name),
        embed_model_id=source.get("EMBED_MODEL_ID", defaults.embed_model_id),
        generation_model_id=source.get("GENERATION_MODEL_ID", defaults.generation_model_id),
        embedding_dimensions=_read_int(
            source, "EMBEDDING_DIMENSIONS", defaults.embedding_dimensions
        ),
        retrieval_top_k_initial=_read_int(
            source, "RETRIEVAL_TOP_K_INITIAL", defaults.retrieval_top_k_initial
        ),
        retrieval_similarity_threshold=_read_float(
            source, "RETRIEVAL_SIMILARITY_THRESHOLD", defaults.retrieval_similarity_threshold
        ),
        retrieval_top_k_final=_read_int(
            source, "RETRIEVAL_TOP_K_FINAL", defaults.retrieval_top_k_final
        ),
        session_question_limit=_read_int(
            source, "SESSION_QUESTION_LIMIT", defaults.session_question_limit
        ),
        session_ttl_hours=_read_int(source, "SESSION_TTL_HOURS", defaults.session_ttl_hours),
    )
