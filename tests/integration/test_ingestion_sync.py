"""Integration tests: full corpus sync against an in-memory (moto) S3."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import boto3
import pytest
from moto import mock_aws
from mypy_boto3_s3 import S3Client

from rag_aws.ingestion.config import RepoConfig
from rag_aws.ingestion.manifest import load_manifest
from rag_aws.ingestion.sync import RepoFetcher, sync_corpus

REGION = "eu-west-1"
BUCKET = "test-project-bucket"


@pytest.fixture
def s3_client() -> Iterator[S3Client]:
    with mock_aws():
        client = boto3.client("s3", region_name=REGION)
        client.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-west-1"},
        )
        yield client


def _make_repo(root: Path, files: dict[str, str]) -> Path:
    """Write ``files`` (relative path → content) under ``root/doc_source``."""
    for relative, content in files.items():
        path = root / "doc_source" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def _fetcher(checkouts: dict[str, Path]) -> RepoFetcher:
    """Return a fetcher that maps repo name → an already-prepared checkout."""

    def fetch(repo: RepoConfig, _workdir: Path) -> Path:
        return checkouts[repo.name]

    return fetch


def _list_raw_keys(s3_client: S3Client) -> set[str]:
    response = s3_client.list_objects_v2(Bucket=BUCKET, Prefix="corpus/raw/")
    return {obj["Key"] for obj in response.get("Contents", [])}


def test_sync_uploads_files_and_writes_manifest(s3_client: S3Client, tmp_path: Path) -> None:
    repo = RepoConfig("demo", url="local")
    checkout = _make_repo(tmp_path / "demo", {"a.md": "alpha", "nested/b.md": "beta"})

    result = sync_corpus(
        s3_client, BUCKET, (repo,), tmp_path, fetch_repo=_fetcher({"demo": checkout})
    )

    assert len(result.plan.to_add) == 2
    assert _list_raw_keys(s3_client) == {
        "corpus/raw/demo/a.md",
        "corpus/raw/demo/nested/b.md",
    }
    manifest = load_manifest(s3_client, BUCKET)
    assert set(manifest.files) == {"corpus/raw/demo/a.md", "corpus/raw/demo/nested/b.md"}


def test_rerun_with_no_changes_is_a_noop(s3_client: S3Client, tmp_path: Path) -> None:
    repo = RepoConfig("demo", url="local")
    checkout = _make_repo(tmp_path / "demo", {"a.md": "alpha"})
    fetch = _fetcher({"demo": checkout})

    sync_corpus(s3_client, BUCKET, (repo,), tmp_path, fetch_repo=fetch)
    second = sync_corpus(s3_client, BUCKET, (repo,), tmp_path, fetch_repo=fetch)

    assert second.plan.has_changes is False
    assert second.plan.unchanged == ["corpus/raw/demo/a.md"]


def test_changed_file_is_updated(s3_client: S3Client, tmp_path: Path) -> None:
    repo = RepoConfig("demo", url="local")
    checkout = _make_repo(tmp_path / "demo", {"a.md": "alpha"})
    fetch = _fetcher({"demo": checkout})
    sync_corpus(s3_client, BUCKET, (repo,), tmp_path, fetch_repo=fetch)

    (checkout / "doc_source" / "a.md").write_text("ALPHA-v2", encoding="utf-8")
    result = sync_corpus(s3_client, BUCKET, (repo,), tmp_path, fetch_repo=fetch)

    assert result.plan.to_update == ["corpus/raw/demo/a.md"]
    body = s3_client.get_object(Bucket=BUCKET, Key="corpus/raw/demo/a.md")["Body"].read()
    assert body == b"ALPHA-v2"


def test_removed_source_file_is_deleted(s3_client: S3Client, tmp_path: Path) -> None:
    repo = RepoConfig("demo", url="local")
    checkout = _make_repo(tmp_path / "demo", {"a.md": "alpha", "b.md": "beta"})
    fetch = _fetcher({"demo": checkout})
    sync_corpus(s3_client, BUCKET, (repo,), tmp_path, fetch_repo=fetch)

    (checkout / "doc_source" / "b.md").unlink()
    result = sync_corpus(s3_client, BUCKET, (repo,), tmp_path, fetch_repo=fetch)

    assert result.plan.to_delete == ["corpus/raw/demo/b.md"]
    assert _list_raw_keys(s3_client) == {"corpus/raw/demo/a.md"}


def test_dry_run_makes_no_writes(s3_client: S3Client, tmp_path: Path) -> None:
    repo = RepoConfig("demo", url="local")
    checkout = _make_repo(tmp_path / "demo", {"a.md": "alpha"})

    result = sync_corpus(
        s3_client,
        BUCKET,
        (repo,),
        tmp_path,
        dry_run=True,
        fetch_repo=_fetcher({"demo": checkout}),
    )

    assert result.dry_run is True
    assert result.plan.to_add == ["corpus/raw/demo/a.md"]
    assert _list_raw_keys(s3_client) == set()  # nothing uploaded
