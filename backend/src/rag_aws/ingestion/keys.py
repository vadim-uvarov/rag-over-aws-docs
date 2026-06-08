"""Mapping between repo-relative markdown paths and S3 object keys."""

from __future__ import annotations

from pathlib import PurePosixPath

from rag_aws.config.settings import RAW_PREFIX


def map_to_raw_key(repo_name: str, relative_path: str) -> str:
    """Map a repo-relative markdown path to its ``corpus/raw/`` object key.

    Args:
        repo_name: Logical repo name (top-level key segment).
        relative_path: Path of the markdown file relative to the ingest root,
            using either OS or POSIX separators.

    Returns:
        An S3 key like ``corpus/raw/<repo>/<path>.md`` with POSIX separators and
        no leading slash.
    """
    # Normalise separators and strip any leading "./" or "/" segments.
    normalised = PurePosixPath(relative_path.replace("\\", "/"))
    parts = [part for part in normalised.parts if part not in ("", ".", "/")]
    return f"{RAW_PREFIX}{repo_name}/{'/'.join(parts)}"
