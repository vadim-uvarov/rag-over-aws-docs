"""Integration tests for SessionQuota against moto DynamoDB."""

from __future__ import annotations

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_dynamodb import DynamoDBClient

from rag_aws.query.session import SessionQuota

TABLE = "sessions"


@pytest.fixture
def dynamodb_client() -> Iterator[DynamoDBClient]:
    with mock_aws():
        client = boto3.client("dynamodb", region_name="eu-west-1")
        client.create_table(
            TableName=TABLE,
            AttributeDefinitions=[{"AttributeName": "session_id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "session_id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield client


def test_counter_increments_and_flips_at_limit(dynamodb_client: DynamoDBClient) -> None:
    quota = SessionQuota(dynamodb_client, TABLE, limit=3, ttl_hours=24)
    results = [quota.record_question("s1") for _ in range(4)]

    assert [usage.used for usage in results] == [1, 2, 3, 4]
    assert [usage.allowed for usage in results] == [True, True, True, False]


def test_sessions_are_independent(dynamodb_client: DynamoDBClient) -> None:
    quota = SessionQuota(dynamodb_client, TABLE, limit=2, ttl_hours=24)
    quota.record_question("a")
    usage_b = quota.record_question("b")
    assert usage_b.used == 1


def test_ttl_is_set_on_first_write(dynamodb_client: DynamoDBClient) -> None:
    quota = SessionQuota(dynamodb_client, TABLE, limit=5, ttl_hours=24)
    quota.record_question("s1", now=1_000_000.0)

    item = dynamodb_client.get_item(TableName=TABLE, Key={"session_id": {"S": "s1"}})["Item"]
    assert int(item["expires_at"]["N"]) == 1_000_000 + 24 * 3600
