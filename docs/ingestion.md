# Corpus ingestion

Mirrors a curated set of AWS documentation repositories into the project S3
bucket under `corpus/raw/` (prefix **A**) and maintains an incremental manifest
under `corpus/manifests/` (prefix **D**).

This runs **locally** for now (PR2). PR8 optionally moves it to a scheduled AWS job.

## How to run

```sh
# Dry run (compute the plan, write nothing) against the bucket in PROJECT_BUCKET_NAME:
PROJECT_BUCKET_NAME=<bucket> uv run python scripts/ingest_corpus.py --dry-run

# Real sync against an explicit bucket:
uv run python scripts/ingest_corpus.py --bucket <bucket>
```

Requirements: AWS credentials with read/write on the bucket, and `git` on PATH
(the script shallow-clones each repo). The region comes from `AWS_REGION`
(default `eu-west-1`).

| Flag | Default | Meaning |
|---|---|---|
| `--bucket` | `PROJECT_BUCKET_NAME` env | Target project bucket |
| `--workdir` | a temp dir | Where repos are checked out |
| `--dry-run` | off | Plan only; no S3 writes |

## What it does

1. **Fetch** each curated repo (shallow clone, or `git pull` if already present).
2. **Discover** markdown files (`.md`) under each repo's `doc_source/` (falls back
   to the repo root if that directory is absent).
3. **Hash** each file's content (SHA-256) and map it to an S3 key
   `corpus/raw/<repo>/<path>.md`.
4. **Diff** the discovered hashes against the manifest to get a plan:
   added / updated / deleted / unchanged.
5. **Apply** (unless `--dry-run`): upload added & changed objects, delete removed
   ones, then rewrite the manifest.

The sync is **idempotent**: a re-run with no source changes uploads nothing.
Deleting a source file removes it from the bucket on the next run.

## Configuring the repo set

Edit `CURATED_REPOS` in `backend/src/rag_aws/ingestion/config.py`. Each entry:

```python
RepoConfig(
    name="amazon-s3-userguide",          # top-level S3 key segment
    url="https://github.com/awsdocs/amazon-s3-userguide.git",
    branch="main",                        # optional
    doc_subdir="doc_source",              # optional; "" scans the whole repo
)
```

Adding a repo only uploads its new files (the diff handles the rest).

## Manifest format

`corpus/manifests/manifest.json`:

```json
{
  "generated_at": "2026-06-08T12:34:56.789Z",
  "files": {
    "corpus/raw/amazon-s3-userguide/Welcome.md": {
      "sha256": "…",
      "source_repo": "amazon-s3-userguide",
      "source_path": "Welcome.md",
      "updated_at": "2026-06-08T12:34:56.789Z"
    }
  }
}
```

`updated_at` is preserved across runs for files whose content did not change.

## Code layout

| Module | Responsibility |
|---|---|
| `ingestion/config.py` | Curated repo list (`RepoConfig`, `CURATED_REPOS`) |
| `ingestion/git_source.py` | Shallow clone/pull |
| `ingestion/discovery.py` | Find markdown files |
| `ingestion/keys.py` | Path → S3 key mapping |
| `ingestion/hashing.py` | SHA-256 content hash |
| `ingestion/manifest.py` | Manifest model + S3 read/write |
| `ingestion/sync.py` | Pure diff planner + top-level `sync_corpus` |
| `scripts/ingest_corpus.py` | CLI entry point |

## Scheduled ingestion (PR8)

Instead of running locally, the same script can run on a schedule on AWS:

```
EventBridge Scheduler ──► ECS Fargate task (backend/ingestion.Dockerfile)
                            └─ incremental sync → corpus/raw/ → existing ETL trigger
```

`terraform/modules/scheduled-ingestion` provisions the ECS cluster, the Fargate
task definition (least-privilege task role), the schedule (default
`rate(24 hours)`), and a failed-run SNS alert. The container just runs
`scripts/ingest_corpus.py` with `PROJECT_BUCKET_NAME` set, so the incremental
manifest logic is identical to a local run — only added/changed files are
uploaded and deletions removed, which the ETL pipeline (PR4) consumes.

Gated behind `enable_scheduled_ingestion`; provide `ingestion_image_uri`,
`ingestion_subnet_ids`, and `ingestion_security_group_ids`.
