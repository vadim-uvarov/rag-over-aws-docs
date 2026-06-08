"""Content hashing used to detect added/changed files between sync runs."""

from __future__ import annotations

import hashlib


def compute_content_hash(data: bytes) -> str:
    """Return the SHA-256 hex digest of ``data``.

    A content hash (rather than a timestamp or size) lets the sync treat a file
    whose bytes are unchanged as a no-op even if its mtime changed.
    """
    return hashlib.sha256(data).hexdigest()
