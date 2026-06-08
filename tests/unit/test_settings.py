"""Unit tests for the settings loader."""

from __future__ import annotations

import pytest

from rag_aws.config import (
    EMBEDDING_DIMENSIONS,
    NOVA_MICRO_MODEL_ID,
    TITAN_EMBED_MODEL_ID,
    Settings,
    load_settings,
)


def test_load_settings_uses_defaults_for_empty_env() -> None:
    """Smoke test: with no overrides, the locked-in defaults are returned."""
    settings = load_settings(env={})
    assert settings.aws_region == "eu-west-1"
    assert settings.embed_model_id == TITAN_EMBED_MODEL_ID
    assert settings.generation_model_id == NOVA_MICRO_MODEL_ID
    assert settings.embedding_dimensions == EMBEDDING_DIMENSIONS
    assert settings.retrieval_similarity_threshold == 0.7
    assert settings.session_question_limit == 20


def test_load_settings_applies_overrides() -> None:
    settings = load_settings(
        env={
            "AWS_REGION": "us-east-1",
            "PROJECT_BUCKET_NAME": "my-bucket",
            "RETRIEVAL_TOP_K_FINAL": "3",
            "RETRIEVAL_SIMILARITY_THRESHOLD": "0.85",
            "SESSION_QUESTION_LIMIT": "5",
        }
    )
    assert settings.aws_region == "us-east-1"
    assert settings.bucket_name == "my-bucket"
    assert settings.retrieval_top_k_final == 3
    assert settings.retrieval_similarity_threshold == 0.85
    assert settings.session_question_limit == 5


def test_settings_is_immutable() -> None:
    settings = load_settings(env={})
    with pytest.raises((AttributeError, TypeError)):
        settings.aws_region = "us-east-1"  # type: ignore[misc]


def test_load_settings_rejects_invalid_int() -> None:
    with pytest.raises(ValueError, match="RETRIEVAL_TOP_K_FINAL"):
        load_settings(env={"RETRIEVAL_TOP_K_FINAL": "not-a-number"})


def test_load_settings_rejects_invalid_float() -> None:
    with pytest.raises(ValueError, match="RETRIEVAL_SIMILARITY_THRESHOLD"):
        load_settings(env={"RETRIEVAL_SIMILARITY_THRESHOLD": "high"})


def test_settings_defaults_match_dataclass_defaults() -> None:
    # load_settings({}) must equal a plain Settings() with no surprises.
    assert load_settings(env={}) == Settings()
