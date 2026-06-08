"""Smoke test verifying the backend package imports."""

from __future__ import annotations

import rag_aws


def test_package_exposes_version() -> None:
    assert isinstance(rag_aws.__version__, str)
    assert rag_aws.__version__
