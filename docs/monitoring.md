# Monitoring & observability

Operational visibility and cost safety across the ETL and query stacks
(`terraform/modules/monitoring`). Gated behind `enable_monitoring`, which the prod
deploy pipeline sets to `true` (the default stays `false` for local applies and PR
plans). See [`architecture.md`](architecture.md#deploy-sequence).

## Structured logging

The Lambdas log one JSON object per line via
`rag_aws.observability.get_logger` (`JsonFormatter`): `timestamp` (ISO-8601 UTC
ms `Z`), `level`, `logger`, `message`, plus any `extra={…}` fields and
`exception`. Query them in CloudWatch Logs Insights, e.g.:

```
fields @timestamp, level, message, key, chunks
| filter level = "ERROR"
| sort @timestamp desc
```

Log groups have bounded retention (`log_retention_days`).

The query handler logs one line per downstream stage — `building dependencies` →
`connecting vector index` / `vector index connected` → `recording session quota`
→ `retrieving chunks` → `generating answer` → `recording trace` → `handled /ask`.
A timeout produces no traceback, so the **last** stage logged before the function
stops is the call that hung (e.g. stopping after `connecting vector index` points
at the cold S3/LanceDB read).

## Fast-fail AWS timeouts

The query Lambda's boto3 clients (Bedrock, DynamoDB, Secrets Manager) and the
Nova generation client use a shared botocore config (`connect_timeout=3`,
`read_timeout=20`, `max_attempts=2`). A stuck downstream call therefore raises a
clear error well under the API Gateway 29s limit instead of riding to the
Lambda's 30s timeout (which the caller only sees as an opaque 504).

## Dashboard

`…-overview` has four widgets: API requests/4XX/5XX/p95 latency · query Lambda
duration/errors/throttles · Step Functions success/failure + DLQ depth · Bedrock
invocations/throttles.

## Alarms → SNS (`…-alerts`)

| Alarm | Condition |
|---|---|
| `…-sfn-failed-executions` | Step Functions `ExecutionsFailed > 0` |
| `…-etl-dlq-not-empty` | DLQ `ApproximateNumberOfMessagesVisible > 0` |
| `…-api-5xx` | API Gateway `5XXError` over threshold |
| `…-bedrock-throttles` | Bedrock `InvocationThrottles > 0` |
| `<function>-errors` | per-Lambda `Errors > 0` |

The Bedrock **cost** budget alarm is in the `query-api` module (PR5). The prod
pipeline leaves `alarm_email` unset, so the SNS topic has **no email subscription** —
set `alarm_email` (or subscribe an endpoint to the topic) to receive notifications.

## Tracing

- **X-Ray** is enabled on the API stage and all Lambdas (`tracing_config`
  Active), so request traces span API → Lambda.
- **Langfuse** captures RAG-quality traces (question, retrieved chunk ids,
  answer) — see its Cloud dashboards.

## Runbook

| Symptom | Likely cause | Action |
|---|---|---|
| `etl-dlq-not-empty` | A file repeatedly fails chunk/embed/index | Inspect the DLQ message + the process Lambda logs (filter by `key`). Fix the cause, then re-drive the DLQ back onto the ingest queue. |
| `sfn-failed-executions` | Bedrock throttling or a bad batch item | Open the failed execution; check the `ProcessDocument` task error. Throttling → lower `map_max_concurrency`; bad item → fix the source doc. |
| `api-5xx` / 504 | Query Lambda errors / timeouts / cold LanceDB | Find the **last per-stage log line** before the function stopped to localise the hang; cross-check the X-Ray subsegments. Verify the vector store exists and the index is populated (run the backfill). |
| `bedrock-throttles` | Burst of requests or low quota | Reduce concurrency; request a Bedrock quota increase. |
| Budget alarm | Bedrock spend over threshold | Review usage in Cost Explorer; tighten the per-session/daily caps. |
| All answers are "I don't know" | Empty/missing vector store | Confirm ingestion ran and the backfill indexed `corpus/raw/` into `corpus/vector-store/`. |
