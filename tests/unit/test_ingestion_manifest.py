"""Unit tests for the ingestion manifest model."""

from __future__ import annotations

from rag_aws.ingestion.hashing import compute_content_hash
from rag_aws.ingestion.manifest import FileEntry, Manifest


def test_compute_content_hash_is_stable_and_distinct() -> None:
    assert compute_content_hash(b"hello") == compute_content_hash(b"hello")
    assert compute_content_hash(b"hello") != compute_content_hash(b"world")


def test_manifest_roundtrips_through_json() -> None:
    manifest = Manifest(
        files={
            "corpus/raw/repo/a.md": FileEntry(
                sha256="abc",
                source_repo="repo",
                source_path="a.md",
                updated_at="2026-01-01T00:00:00.000Z",
            )
        },
        generated_at="2026-01-01T00:00:00.000Z",
    )
    restored = Manifest.from_json(manifest.to_json())
    assert restored == manifest


def test_manifest_hashes_view() -> None:
    manifest = Manifest(
        files={
            "k1": FileEntry("h1", "repo", "a.md", "2026-01-01T00:00:00.000Z"),
            "k2": FileEntry("h2", "repo", "b.md", "2026-01-01T00:00:00.000Z"),
        }
    )
    assert manifest.hashes() == {"k1": "h1", "k2": "h2"}


def test_empty_manifest_from_blank_json() -> None:
    assert Manifest.from_json('{"files": {}}').files == {}
