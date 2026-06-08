"""Per-session question quota backed by DynamoDB.

Each session gets a counter with a 24h TTL; once it exceeds the limit the API
returns 429. The counter is incremented atomically and the TTL is set once.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_dynamodb import DynamoDBClient

SESSION_KEY_ATTR = "session_id"
COUNT_ATTR = "count"
EXPIRES_ATTR = "expires_at"


@dataclass(frozen=True)
class SessionUsage:
    """Outcome of recording one question against a session's quota."""

    session_id: str
    used: int
    limit: int
    allowed: bool


def evaluate_quota(used: int, limit: int) -> bool:
    """Allow the question iff the new usage count is within the limit (``used <= limit``)."""
    return used <= limit


class SessionQuota:
    """DynamoDB-backed counter enforcing N questions per session within a TTL window."""

    def __init__(
        self,
        dynamodb_client: DynamoDBClient,
        table_name: str,
        limit: int,
        ttl_hours: int,
    ) -> None:
        self._client = dynamodb_client
        self._table_name = table_name
        self._limit = limit
        self._ttl_seconds = ttl_hours * 3600

    def record_question(self, session_id: str, now: float | None = None) -> SessionUsage:
        """Atomically increment the session counter and report whether it's allowed."""
        current_time = time.time() if now is None else now
        expires_at = int(current_time) + self._ttl_seconds
        response = self._client.update_item(
            TableName=self._table_name,
            Key={SESSION_KEY_ATTR: {"S": session_id}},
            UpdateExpression=(
                f"ADD #count :one SET {EXPIRES_ATTR} = if_not_exists({EXPIRES_ATTR}, :exp)"
            ),
            ExpressionAttributeNames={"#count": COUNT_ATTR},
            ExpressionAttributeValues={
                ":one": {"N": "1"},
                ":exp": {"N": str(expires_at)},
            },
            ReturnValues="ALL_NEW",
        )
        used = int(response["Attributes"][COUNT_ATTR]["N"])
        return SessionUsage(
            session_id=session_id,
            used=used,
            limit=self._limit,
            allowed=evaluate_quota(used, self._limit),
        )
