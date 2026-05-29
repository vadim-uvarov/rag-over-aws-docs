"""Smoke tests verifying the package imports and exposes basic metadata."""

import rag_over_aws_docs


def test_package_imports() -> None:
    """The package imports and exposes a version string."""
    assert isinstance(rag_over_aws_docs.__version__, str)
    assert rag_over_aws_docs.__version__
