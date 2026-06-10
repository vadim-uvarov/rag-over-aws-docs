"""Build a human-facing link to the parent document of a chunk."""

from __future__ import annotations

# awsdocs repos are mirrored 1:1, so a chunk's repo + source_doc maps to a GitHub URL.
_GITHUB_DOC_URL = "https://github.com/awsdocs/{repo}/blob/main/doc_source/{source_doc}"


def build_doc_link(repo: str, source_doc: str) -> str:
    """Return a best-effort link to the source document on GitHub."""
    return _GITHUB_DOC_URL.format(repo=repo, source_doc=source_doc)
