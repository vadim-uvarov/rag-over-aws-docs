"""Incremental, hash-based corpus sync into the project bucket.

The diff logic (:func:`build_sync_plan`) is a pure function over content hashes,
so it is fully unit-testable. :func:`sync_corpus` wires it to git checkouts, the
filesystem, and S3.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from rag_aws.config.timestamps import format_timestamp
from rag_aws.ingestion.config import RepoConfig
from rag_aws.ingestion.discovery import discover_markdown_files
from rag_aws.ingestion.git_source import sync_repo_to_local
from rag_aws.ingestion.hashing import compute_content_hash
from rag_aws.ingestion.keys import map_to_raw_key
from rag_aws.ingestion.manifest import FileEntry, Manifest, load_manifest, save_manifest

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

# Fetches a repo to a local checkout; injectable so tests can skip real git.
RepoFetcher = Callable[[RepoConfig, Path], Path]

_MARKDOWN_CONTENT_TYPE = "text/markdown"


@dataclass
class SyncPlan:
    """The set of S3 keys to add, update, delete, or leave unchanged."""

    to_add: list[str] = field(default_factory=list)
    to_update: list[str] = field(default_factory=list)
    to_delete: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.to_add or self.to_update or self.to_delete)


@dataclass
class SyncResult:
    """Outcome of a sync run."""

    plan: SyncPlan
    dry_run: bool

    def summary(self) -> str:
        verb = "would" if self.dry_run else "did"
        return (
            f"sync {verb} add={len(self.plan.to_add)} "
            f"update={len(self.plan.to_update)} delete={len(self.plan.to_delete)} "
            f"unchanged={len(self.plan.unchanged)}"
        )


def build_sync_plan(desired: Mapping[str, str], current: Mapping[str, str]) -> SyncPlan:
    """Diff desired vs. current ``{s3_key: content_hash}`` maps.

    Args:
        desired: Hashes for the files discovered in the source repos this run.
        current: Hashes recorded in the existing manifest.

    Returns:
        A :class:`SyncPlan` partitioning keys into add / update / delete /
        unchanged (each list sorted for deterministic execution).
    """
    to_add: list[str] = []
    to_update: list[str] = []
    unchanged: list[str] = []
    for key, content_hash in desired.items():
        if key not in current:
            to_add.append(key)
        elif current[key] != content_hash:
            to_update.append(key)
        else:
            unchanged.append(key)
    to_delete = [key for key in current if key not in desired]
    return SyncPlan(
        to_add=sorted(to_add),
        to_update=sorted(to_update),
        to_delete=sorted(to_delete),
        unchanged=sorted(unchanged),
    )


@dataclass
class _DiscoveredFile:
    """A markdown file found in a source repo, ready to sync."""

    content: bytes
    content_hash: str
    source_repo: str
    source_path: str


def _collect_desired_files(
    repos: tuple[RepoConfig, ...],
    workdir: Path,
    fetch_repo: RepoFetcher,
) -> dict[str, _DiscoveredFile]:
    """Fetch every repo and read its markdown into a ``{s3_key: file}`` map."""
    discovered: dict[str, _DiscoveredFile] = {}
    for repo in repos:
        local_checkout = fetch_repo(repo, workdir)
        for absolute_path, relative_path in discover_markdown_files(
            local_checkout, repo.doc_subdir
        ):
            content = absolute_path.read_bytes()
            key = map_to_raw_key(repo.name, relative_path)
            discovered[key] = _DiscoveredFile(
                content=content,
                content_hash=compute_content_hash(content),
                source_repo=repo.name,
                source_path=relative_path,
            )
    return discovered


def _build_manifest(
    discovered: dict[str, _DiscoveredFile],
    plan: SyncPlan,
    previous: Manifest,
    now: str,
) -> Manifest:
    """Build the new manifest, preserving timestamps of unchanged files."""
    files: dict[str, FileEntry] = {}
    unchanged_keys = set(plan.unchanged)
    for key, discovered_file in discovered.items():
        if key in unchanged_keys and key in previous.files:
            files[key] = previous.files[key]  # keep original updated_at
        else:
            files[key] = FileEntry(
                sha256=discovered_file.content_hash,
                source_repo=discovered_file.source_repo,
                source_path=discovered_file.source_path,
                updated_at=now,
            )
    return Manifest(files=files)


def sync_corpus(
    s3_client: S3Client,
    bucket: str,
    repos: tuple[RepoConfig, ...],
    workdir: Path,
    *,
    dry_run: bool = False,
    fetch_repo: RepoFetcher = sync_repo_to_local,
) -> SyncResult:
    """Mirror the curated repos' markdown into ``corpus/raw/`` incrementally.

    Reads the existing manifest, diffs it against the freshly discovered files,
    then (unless ``dry_run``) uploads added/changed objects, deletes removed ones,
    and rewrites the manifest. Re-running with no source changes is a no-op.

    Args:
        s3_client: Boto3 S3 client.
        bucket: Project bucket name.
        repos: Curated repositories to ingest.
        workdir: Local directory for repo checkouts.
        dry_run: When true, compute the plan but make no S3 writes.
        fetch_repo: Strategy for obtaining a local checkout (injectable for tests).

    Returns:
        A :class:`SyncResult` describing what changed (or would change).
    """
    discovered = _collect_desired_files(repos, workdir, fetch_repo)
    desired_hashes = {key: file.content_hash for key, file in discovered.items()}

    manifest = load_manifest(s3_client, bucket)
    plan = build_sync_plan(desired_hashes, manifest.hashes())

    if dry_run:
        return SyncResult(plan=plan, dry_run=True)

    for key in (*plan.to_add, *plan.to_update):
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=discovered[key].content,
            ContentType=_MARKDOWN_CONTENT_TYPE,
        )
    for key in plan.to_delete:
        s3_client.delete_object(Bucket=bucket, Key=key)

    new_manifest = _build_manifest(discovered, plan, manifest, format_timestamp())
    save_manifest(s3_client, bucket, new_manifest)

    return SyncResult(plan=plan, dry_run=False)
