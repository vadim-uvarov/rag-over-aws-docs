"""Unit tests for repo-path → S3 key mapping."""

from __future__ import annotations

import pytest

from rag_aws.ingestion.keys import map_to_raw_key, parse_raw_key


def test_map_to_raw_key_builds_prefixed_posix_key() -> None:
    assert (
        map_to_raw_key("amazon-s3-userguide", "Welcome.md")
        == "corpus/raw/amazon-s3-userguide/Welcome.md"
    )


def test_map_to_raw_key_preserves_nested_paths() -> None:
    assert (
        map_to_raw_key("iam-user-guide", "guides/intro/Overview.md")
        == "corpus/raw/iam-user-guide/guides/intro/Overview.md"
    )


def test_map_to_raw_key_normalises_windows_separators() -> None:
    assert map_to_raw_key("repo", "a\\b\\c.md") == "corpus/raw/repo/a/b/c.md"


def test_map_to_raw_key_strips_leading_dot_and_slash_segments() -> None:
    assert map_to_raw_key("repo", "./docs/x.md") == "corpus/raw/repo/docs/x.md"
    assert map_to_raw_key("repo", "/docs/x.md") == "corpus/raw/repo/docs/x.md"


def test_parse_raw_key_inverts_map_to_raw_key() -> None:
    assert parse_raw_key("corpus/raw/iam-user-guide/guides/intro.md") == (
        "iam-user-guide",
        "guides/intro.md",
    )


def test_parse_raw_key_round_trips() -> None:
    repo, doc = "amazon-s3-userguide", "Welcome.md"
    assert parse_raw_key(map_to_raw_key(repo, doc)) == (repo, doc)


def test_parse_raw_key_rejects_keys_outside_prefix() -> None:
    with pytest.raises(ValueError, match="corpus/raw/"):
        parse_raw_key("web/index.html")


def test_parse_raw_key_rejects_keys_without_document() -> None:
    with pytest.raises(ValueError, match="structure"):
        parse_raw_key("corpus/raw/just-a-repo")
