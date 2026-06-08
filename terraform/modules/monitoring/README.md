# monitoring module

Operational visibility and alerting across the ETL and query stacks.

- **SNS** `…-alerts` (optional email subscription) — destination for all alarms.
- **Alarms** → SNS:
  - Step Functions `ExecutionsFailed > 0`
  - ETL DLQ `ApproximateNumberOfMessagesVisible > 0`
  - API Gateway `5XXError` spike
  - Bedrock `InvocationThrottles > 0`
  - Per-Lambda `Errors > 0`
- **Dashboard** `…-overview` — API traffic/4XX/5XX/latency, query Lambda
  duration/errors/throttles, Step Functions success/failure + DLQ depth, and
  Bedrock invocations/throttles.

X-Ray tracing is enabled on the Lambdas and the API stage in the `etl` and
`query-api` modules. Langfuse provides RAG-quality dashboards (PR5).

## Usage

Gated behind `enable_monitoring` in `terraform/prod`; requires `enable_etl` and
`enable_query_api` so the monitored resources exist. Inputs are wired from those
modules' outputs (state machine ARN, DLQ name, API name, Lambda names).

The Bedrock **cost** budget alarm lives in the `query-api` module (PR5).
