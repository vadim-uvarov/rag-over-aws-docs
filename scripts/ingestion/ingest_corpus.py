#!/usr/bin/env python3
"""Mirror the curated AWS documentation repos into the project S3 bucket.

Run locally (PR2). Reads/writes the manifest at ``corpus/manifests/manifest.json``
and performs an incremental, hash-based sync into ``corpus/raw/``.

Examples:
    python scripts/ingestion/ingest_corpus.py --bucket my-bucket
    python scripts/ingestion/ingest_corpus.py --dry-run            # uses PROJECT_BUCKET_NAME
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

# The package is not pip-installed (no build backend); make it importable when
# this script is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend" / "src"))

import boto3

from rag_aws.config.settings import load_settings
from rag_aws.ingestion.config import CURATED_REPOS
from rag_aws.ingestion.sync import sync_corpus


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bucket",
        default=None,
        help="Project bucket name (defaults to PROJECT_BUCKET_NAME from the environment).",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="Directory for repo checkouts (defaults to a temp dir).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the sync plan without writing to S3.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: run the corpus sync and print a summary."""
    args = parse_args(argv)
    settings = load_settings()
    bucket = args.bucket or settings.bucket_name
    if not bucket:
        print(
            "No bucket given. Pass --bucket or set PROJECT_BUCKET_NAME.",
            file=sys.stderr,
        )
        return 2

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    workdir = args.workdir or Path(tempfile.mkdtemp(prefix="awsdocs-"))
    workdir.mkdir(parents=True, exist_ok=True)

    result = sync_corpus(
        s3_client,
        bucket=bucket,
        repos=CURATED_REPOS,
        workdir=workdir,
        dry_run=args.dry_run,
    )
    print(result.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
