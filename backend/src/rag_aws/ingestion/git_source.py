"""Fetch source repositories to a local working directory via git."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rag_aws.ingestion.config import RepoConfig


def sync_repo_to_local(repo: RepoConfig, workdir: Path) -> Path:
    """Ensure ``repo`` is checked out under ``workdir`` and return its path.

    Performs a shallow clone on first use and a shallow pull on subsequent runs,
    keeping the local copy small and the operation re-runnable.

    Args:
        repo: Repository to fetch.
        workdir: Parent directory holding all repo checkouts.

    Returns:
        Path to the local checkout of ``repo``.
    """
    destination = workdir / repo.name
    if (destination / ".git").is_dir():
        _run_git(["-C", str(destination), "pull", "--depth", "1", "--ff-only"])
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _run_git(["clone", "--depth", "1", "--branch", repo.branch, repo.url, str(destination)])
    return destination


def _run_git(args: list[str]) -> None:
    """Run a git command, raising with captured output on failure."""
    subprocess.run(["git", *args], check=True, capture_output=True, text=True)
