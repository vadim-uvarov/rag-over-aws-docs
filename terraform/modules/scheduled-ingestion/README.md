# scheduled-ingestion module

Runs the PR2 corpus ingestion (`scripts/ingest_corpus.py`) on a schedule instead
of locally, so the corpus refreshes automatically and changed files flow through
the existing ETL trigger.

```
EventBridge Scheduler ──(rate/cron)──► ECS Fargate task (ingestion image)
                                          └─ incremental sync → S3 corpus/raw/ (A)
                                             (manifest diff → S3 ObjectCreated/Removed → ETL)
ECS Task State Change (non-zero exit) ──► EventBridge ──► SNS (failed-run alert)
```

- **ECS Fargate** task from `backend/ingestion.Dockerfile` (git + the ingestion
  lib); least-privilege task role (read/write the bucket, KMS).
- **EventBridge Scheduler** invokes `RunTask` on `schedule_expression`
  (default `rate(24 hours)`).
- **Failed-run alert** — an EventBridge rule on stopped tasks with a non-zero
  exit code publishes to SNS (optional email).

The incremental manifest logic is unchanged, so a scheduled run uploads only
added/changed files and removes deleted ones — the same `corpus/raw/` events the
ETL pipeline already consumes (PR4).

## Usage

Provide `image_uri` (in ECR), `subnet_ids`, and `security_group_ids` (the task
needs outbound internet for git + S3). Gated behind `enable_scheduled_ingestion`
in `terraform/prod`.

## Tests

Reuses the PR2 ingestion test suite (the containerized code is identical);
`terraform validate` covers the infrastructure.
