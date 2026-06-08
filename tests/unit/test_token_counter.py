"""Unit tests for the tiktoken token counter.

Note: the first ``count_tokens`` may download the cl100k_base vocab; CI has
network access.
"""

from __future__ import annotations

from rag_aws.etl.chunking.token_counter import TiktokenCounter


def test_empty_text_has_zero_tokens() -> None:
    assert TiktokenCounter().count_tokens("") == 0


def test_nonempty_text_has_positive_token_count() -> None:
    counter = TiktokenCounter()
    assert counter.count_tokens("hello world") > 0


def test_token_count_is_deterministic() -> None:
    counter = TiktokenCounter()
    assert counter.count_tokens("the quick brown fox") == counter.count_tokens(
        "the quick brown fox"
    )


def test_longer_text_has_at_least_as_many_tokens() -> None:
    counter = TiktokenCounter()
    assert counter.count_tokens("a b c d e") >= counter.count_tokens("a b")
