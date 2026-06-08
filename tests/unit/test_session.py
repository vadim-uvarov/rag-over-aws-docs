"""Unit tests for the pure session-quota decision."""

from __future__ import annotations

from rag_aws.query.session import evaluate_quota


def test_under_limit_is_allowed() -> None:
    assert evaluate_quota(used=1, limit=20) is True


def test_at_limit_is_allowed() -> None:
    # The 20th question (used == limit) is still allowed.
    assert evaluate_quota(used=20, limit=20) is True


def test_over_limit_is_rejected() -> None:
    # The 21st question is rejected.
    assert evaluate_quota(used=21, limit=20) is False
