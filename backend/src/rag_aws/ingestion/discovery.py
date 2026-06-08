"""Discover the markdown files to ingest from a checked-out repository."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

_MARKDOWN_SUFFIX = ".md"


def discover_markdown_files(repo_root: Path, doc_subdir: str = "") -> Iterator[tuple[Path, str]]:
    """Yield ``(absolute_path, relative_path)`` for each markdown file to ingest.

    Args:
        repo_root: Local checkout root of the repository.
        doc_subdir: If set and it exists, only files under this sub-directory are
            yielded and relative paths are computed from it; otherwise the whole
            repo is scanned relative to ``repo_root``.

    Yields:
        Tuples of the file's absolute path and its POSIX relative path (the basis
        for the S3 key), in sorted order for deterministic runs.
    """
    search_root = repo_root / doc_subdir if doc_subdir else repo_root
    if not search_root.is_dir():
        # Fall back to the repo root when the configured subdir is absent.
        search_root = repo_root

    for path in sorted(search_root.rglob(f"*{_MARKDOWN_SUFFIX}")):
        if path.is_file():
            relative = path.relative_to(search_root).as_posix()
            yield path, relative
