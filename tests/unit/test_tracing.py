"""Unit tests for Langfuse key loading and best-effort tracing."""

from __future__ import annotations

import json
from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_secretsmanager import SecretsManagerClient

from rag_aws.query.tracing import load_langfuse_keys, record_query_trace

SECRET_NAME = "langfuse/keys"


@pytest.fixture
def secrets_client() -> Iterator[SecretsManagerClient]:
    with mock_aws():
        yield boto3.client("secretsmanager", region_name="eu-west-1")


def test_loads_valid_keys(secrets_client: SecretsManagerClient) -> None:
    secrets_client.create_secret(
        Name=SECRET_NAME,
        SecretString=json.dumps({"public_key": "pk", "secret_key": "sk", "host": "https://h"}),
    )
    keys = load_langfuse_keys(secrets_client, SECRET_NAME)
    assert keys is not None
    assert (keys.public_key, keys.secret_key, keys.host) == ("pk", "sk", "https://h")


def test_missing_secret_returns_none(secrets_client: SecretsManagerClient) -> None:
    assert load_langfuse_keys(secrets_client, "does-not-exist") is None


def test_incomplete_keys_return_none(secrets_client: SecretsManagerClient) -> None:
    secrets_client.create_secret(Name=SECRET_NAME, SecretString=json.dumps({"public_key": "pk"}))
    assert load_langfuse_keys(secrets_client, SECRET_NAME) is None


def test_record_trace_without_keys_is_noop() -> None:
    assert record_query_trace(None, question="q", chunks=[], answer="a") is False
