# etl module

Event-driven, batched, resilient processing of changed corpus files:

```
S3 corpus/raw/ ──(EventBridge: Object Created/Deleted)──► SQS ingest (+ DLQ)
                                                            │ (batch)
                                       Lambda dispatch ◄────┘
                                            │ StartExecution
                                            ▼
                          Step Functions: Map(items) ─► Lambda process
                                                          (chunk → embed → index)
```

- **SQS** `…-etl-ingest` buffers events; a **DLQ** captures messages that fail
  `maxReceiveCount` times.
- **EventBridge** rule matches `Object Created`/`Object Deleted` under
  `corpus/raw/` and targets the queue (the bucket has EventBridge notifications
  enabled here).
- **dispatch** Lambda (SQS-triggered, batched) starts one Step Functions
  execution per batch with `{"items":[…]}`.
- **Step Functions** runs an inline **Map** (bounded `MaxConcurrency` to avoid
  Bedrock throttling) invoking the **process** Lambda per item, with per-task
  retry/backoff and a tolerated-failure budget.
- Both Lambdas run from **one container image** (LanceDB/pyarrow are too heavy
  for a zip), selected by `image_config.command`.

## Container image

The Lambdas need an image in ECR built from `backend/Dockerfile`. Until one
exists, keep `enable_etl = false` in the root stack (see `terraform/prod`). The
DLQ-not-empty and failed-execution alarms are wired in PR7.

## Key inputs

| Name | Description |
|---|---|
| `name_prefix` | Resource name prefix |
| `bucket_name` / `bucket_arn` / `kms_key_arn` | Project bucket + its key |
| `lambda_image_uri` | ECR image URI for both Lambdas |
| `map_max_concurrency` | Concurrent processors (throttling control) |

## Key outputs

| Name | Description |
|---|---|
| `ingest_queue_url` | Backfill target (`scripts/backfill.py --queue-url`) |
| `state_machine_arn` | ETL state machine |
| `dlq_arn` | Dead-letter queue |
