"""Unit tests for markdown file discovery."""

from __future__ import annotations

from pathlib import Path

from rag_aws.ingestion.discovery import discover_markdown_files


def _write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_discover_only_markdown_under_subdir(tmp_path: Path) -> None:
    _write(tmp_path / "doc_source" / "a.md")
    _write(tmp_path / "doc_source" / "nested" / "b.md")
    _write(tmp_path / "doc_source" / "image.png")
    _write(tmp_path / "README.md")  # outside doc_source, must be ignored

    found = {relative for _, relative in discover_markdown_files(tmp_path, "doc_source")}
    assert found == {"a.md", "nested/b.md"}


def test_discover_falls_back_to_repo_root_when_subdir_missing(tmp_path: Path) -> None:
    _write(tmp_path / "a.md")
    found = {relative for _, relative in discover_markdown_files(tmp_path, "doc_source")}
    assert found == {"a.md"}


def test_discover_empty_repo_yields_nothing(tmp_path: Path) -> None:
    assert list(discover_markdown_files(tmp_path, "")) == []
