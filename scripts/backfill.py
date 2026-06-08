#!/usr/bin/env python3
"""Enqueue all objects in ``corpus/raw/`` onto the ETL SQS buffer.

Use for the initial bulk load after ingesting the corpus (PR2), so existing
objects flow through the same chunk → embed → index pipeline as live changes.

Example:
    python scripts/backfill.py --bucket my-bucket --queue-url https://sqs...
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "src"))

import boto3

from rag_aws.config.settings import load_settings
from rag_aws.etl.backfill import SqsClient, enqueue_backfill


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default=None, help="Project bucket (PROJECT_BUCKET_NAME).")
    parser.add_argument("--queue-url", required=True, help="ETL ingestion SQS queue URL.")
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds to pause between 10-message batches (throttle control).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    bucket = args.bucket or settings.bucket_name
    if not bucket:
        print("No bucket given. Pass --bucket or set PROJECT_BUCKET_NAME.", file=sys.stderr)
        return 2

    s3_client = boto3.client("s3", region_name=settings.aws_region)
    sqs_client = cast(SqsClient, boto3.client("sqs", region_name=settings.aws_region))
    count = enqueue_backfill(
        s3_client,
        sqs_client,
        bucket=bucket,
        queue_url=args.queue_url,
        inter_batch_delay_seconds=args.delay,
    )
    print(f"enqueued {count} objects for backfill")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
