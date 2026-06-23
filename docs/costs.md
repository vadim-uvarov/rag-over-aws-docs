# Cost model

What it costs to run this stack, broken into a **fixed** part (always-on,
independent of traffic) and a **usage** part (scales with questions asked).
All figures are AWS list prices for **eu-west-1** (the region locked in
[`config/deploy.json`](../config/deploy.json)) and are estimates — use the
[AWS Pricing Calculator](https://calculator.aws/) for a binding quote.

> The reference workload below is **20 questions/day (~600/month)**, the
> per-session quota ceiling (`session_question_limit = 20`,
> see [`config/settings.py`](../backend/src/rag_aws/config/settings.py)).

## TL;DR

At 20 questions/day the bill is **~$8–10/month, almost entirely fixed
infrastructure**. Answering the questions themselves (Bedrock + Lambda +
API Gateway) costs **under $0.20/month** — the AI workload is effectively
free at this volume; the fixed baseline dominates.

In the first 12 months the AWS Free Tier covers most of the usage line items
and the CloudWatch alarms, so expect closer to **~$7.50/month**.

## Usage costs (scale with traffic)

Each `/ask` embeds the query (Titan v2), searches LanceDB, generates an answer
(Nova Micro), checks the DynamoDB session quota, and traces to Langfuse. See
[`rag.md`](rag.md) for the flow.

| Component | Basis | ~600 questions/month |
|---|---|---|
| Bedrock — Nova Micro | ~2,600 input tokens (5 × 512-token chunks + prompt) + ~400 output tokens/query | ~$0.09 |
| Bedrock — Titan Embed v2 | ~30 tokens/query embedded | ~$0.0004 |
| Lambda (query) | 2048 MB, ~3–5 s/query (mostly covered by free tier) | $0–0.08 |
| API Gateway (REST) | $3.50 / million requests | ~$0.002 |
| DynamoDB | PAY_PER_REQUEST, ~1 read + 1 write/query | ~$0 |
| CloudFront / X-Ray | well under free tiers | ~$0 |
| **Usage subtotal** | | **≈ $0.10–0.20/month** |

Nova Micro and Titan v2 are the cheapest Bedrock options and were chosen for
exactly that reason (see [`architecture.md`](architecture.md#key-decisions)).
Even a 10× traffic increase (200 questions/day) keeps the usage line at a
couple of dollars.

## Fixed costs (always-on)

These run whether or not anyone asks a question.

| Component | Why it exists | ~Cost/month |
|---|---|---|
| WAF Web ACL | Per-IP rate limiting in front of the API ([`query-api/waf.tf`](../terraform/modules/query-api/waf.tf)) — $5 ACL + $1 rule | ~$6.00 |
| KMS customer-managed key | SSE-KMS at-rest encryption of the project bucket ([`storage/main.tf`](../terraform/modules/storage/main.tf)) | ~$1.00 |
| CloudWatch alarms | ~7 alarms: SFN failures, DLQ depth, API 5XX, Bedrock throttles, 3× Lambda errors ([`monitoring/main.tf`](../terraform/modules/monitoring/main.tf)) | ~$0.70 |
| Secrets Manager | 1 secret holding the Langfuse keys ([`query-api/main.tf`](../terraform/modules/query-api/main.tf)) | ~$0.40 |
| S3 storage | Corpus raw + chunks + LanceDB vector store + web build (versioned, noncurrent versions pruned) | ~$0.20 |
| ECR | The shared Lambda container image | ~$0.10 |
| SNS / Budgets / dashboard | Idle alert topics, 1 Bedrock budget (first 2 free), 1 dashboard (first 3 free) | ~$0 |
| **Fixed subtotal** | | **≈ $8.40/month** |

### WAF is the single biggest line item

At ~$6/month, the WAF web ACL costs more than the entire AI workload. Dropping
it and relying only on the API Gateway usage-plan throttle/quota plus the
per-session DynamoDB quota for abuse control would roughly **halve the bill to
~$2.50/month** — at the cost of losing per-IP rate limiting at the edge.

### The KMS key is optional hardening

S3 is always encrypted; the choice is *which* key. The stack uses a
**customer-managed key** for rotation control, a custom key policy (it grants
CloudFront `kms:Decrypt` to serve the SPA), and CloudTrail-audited decrypts.
For public AWS documentation this is arguably overkill. Cheaper alternatives:

| Option | Key cost | Trade-off |
|---|---|---|
| Customer-managed KMS key (current) | ~$1.00 + requests | Full key control, rotation, audit |
| AWS-managed key (`aws/s3`) | $0 (request charges remain) | Less control, no custom policy |
| SSE-S3 (AES256) | $0 | No KMS at all; still encrypted at rest, public access already blocked |

Switching to SSE-S3 removes the key, its ~$1/month, the KMS request costs, and
the CloudFront decrypt grant.

## Not included here

- **ETL re-ingestion runs.** SQS, Step Functions, and the embedding Lambdas are
  $0 when idle but cost real money each time the corpus is (re)indexed
  (Bedrock Titan embeddings over the whole `awsdocs` corpus + Lambda + Step
  Functions transitions). This is an occasional batch cost, not part of the
  per-question math. See [`etl.md`](etl.md).
- **Langfuse Cloud.** External tracing service on its own plan, not an AWS
  charge.
- **Data egress** beyond CloudFront's free tier, and any custom domain /
  ACM / Route 53 (not provisioned by this stack).

## Levers to cut the bill

1. **Remove WAF** (~$6/month) — biggest single saving; keep the usage-plan and
   session quotas as the abuse controls.
2. **Switch the bucket to SSE-S3** (~$1/month + KMS requests).
3. **Trim CloudWatch alarms** to the few you'll actually act on (~$0.10 each).
4. **Shorten log retention** (`log_retention_days`, default 14) if logs grow.
</content>
</invoke>
