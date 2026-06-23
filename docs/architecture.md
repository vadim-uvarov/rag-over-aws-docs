# Architecture

RAG-over-AWS-docs is a demo web app: a user asks a question about AWS
documentation and an AI agent answers using Retrieval-Augmented Generation (RAG)
over the official `awsdocs` markdown corpus.

> This document tracks the architecture, built out PR-by-PR; see
> `.claude/initial-plan.md` for the full plan. The full stack — storage, the
> ingestion ETL, the synchronous query API, the frontend, and monitoring — is now
> provisioned by the prod deploy pipeline (the `(PRn)` annotations below record when
> each piece landed).

## Data flow

```
                  ┌──────────────── INGESTION (local for now, PR2) ───────────────┐
 awsdocs GitHub ─► clone curated repos ─► extract .md ─► S3 corpus/raw/ (A)
                  (writes content-hash manifest to corpus/manifests/ (D))
                                          │
                            S3 ObjectCreated/Removed events (PR4)
                                          ▼
 EventBridge ─► SQS (buffer, batch) ─► Dispatcher ─► Step Functions (Map over batch)
                                                      │ chunk → corpus/chunks/ (B)
                                                      │ embed → Titan v2 (Bedrock)
                                                      └ index → LanceDB @ corpus/vector-store/ (C)

                  ┌──────────────────────── QUERY (synchronous, PR5/PR6) ──────────┐
 CloudFront ─► S3 web/ (React SPA)
      │
      └─► API Gateway (WAF + usage plan) ─► Query Lambda
                                              ├ session quota check (DynamoDB)
                                              ├ embed query (Titan v2)
                                              ├ LanceDB search: top20 → sim ≥ 0.7 → top5
                                              ├ generate (Nova Micro via LangChain)
                                              ├ trace to Langfuse Cloud
                                              └ return JSON { answer, chunks[] }
```

## Single S3 bucket — prefix layout

One project bucket (versioned, SSE-S3, all public access blocked):

| Placeholder | Prefix | Contents |
|---|---|---|
| **A** | `corpus/raw/` | Raw AWS markdown, key = `<repo>/<path>.md` |
| **B** | `corpus/chunks/` | Plain-text chunks, key = `<repo>/<doc>/<chunk-index>.txt` |
| **C** | `corpus/vector-store/` | LanceDB table(s): embeddings + chunk metadata |
| **D** | `corpus/manifests/` | Ingestion state: per-file content hashes + chunk inventory |
| — | `web/` | Frontend build artifacts (CloudFront origin) |

The bucket is provisioned by `terraform/modules/storage`, composed in
`terraform/prod` alongside the `etl`, `query-api`, `frontend`, and `monitoring`
modules.

## Deploy sequence

The `prod` stack is composed of independently gated modules (`enable_etl`,
`enable_query_api`, `enable_monitoring`, `enable_frontend`). The Terraform variable
defaults stay `false` so `terraform validate`, PR plans, and local applies remain
green without a container image; the prod deploy pipeline overrides them to deploy
the full stack.

1. **Bootstrap (one-time, manual, admin).** `terraform/bootstrap` creates the GitHub
   OIDC provider, the CI/CD deploy role with the permissions the prod apply needs,
   and the shared `rag-aws-etl` ECR repository (immutable tags, scan-on-push,
   lifecycle policy). This **must** be applied before the first prod deploy, or the
   image push fails (repo missing) and `terraform apply` fails with `AccessDenied`.
2. **Build + push image.** The deploy workflow builds one Lambda container image from
   `backend/Dockerfile`, tags it with the deployed commit's short SHA (idempotent on
   rerun), and pushes it to `rag-aws-etl`. The ETL process Lambda, ETL dispatch
   Lambda, and the query-API Lambda all run this **same image** — the handler is
   selected per function via `image_config.command`.
3. **Apply prod.** `terraform apply` runs with `enable_etl`/`enable_query_api`/
   `enable_monitoring`/`enable_frontend` set to `true` and the pushed image URI passed
   to the ETL and query-API Lambdas.

See the README "What the prod pipeline deploys" and "Prerequisites for the first prod
deploy" sections for the full operational checklist (including Bedrock model
availability in `eu-west-1`).

## Key decisions

| Topic | Decision |
|---|---|
| Region | **eu-west-1** — defined once in `config/deploy.json`; both Terraform stacks (`jsondecode`) and the deploy workflow, backend, and credentials (`jq`) derive from it |
| Embedding model | **Amazon Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`), 512-dim |
| Generation model | **Amazon Nova Micro** (`amazon.nova-micro-v1:0`) |
| Vector store | **LanceDB** on S3 |
| API delivery | Synchronous JSON (API Gateway → Lambda) |
| Observability | Langfuse Cloud (keys via Secrets Manager) |

> **Bedrock availability (verify before the first prod deploy):** Amazon Nova Micro
> and Titan Embeddings V2 must be available — with model access enabled — in
> **eu-west-1**. If only cross-region inference profiles are offered there, switch the
> model IDs to their profile IDs (`eu.amazon.*`) in
> `backend/src/rag_aws/config/settings.py` and widen the ETL process role's Bedrock
> statement in `terraform/modules/etl/iam.tf` to allow `inference-profile/*` (the
> query-API role already does). See the README "Prerequisites for the first prod
> deploy".

## Repository layout

```
backend/src/rag_aws/   # Python backend package
  config/              # settings, model ids, timestamp helper
tests/
  unit/  integration/
frontend/              # React SPA (stub in PR1, built in PR6)
terraform/
  modules/storage/     # project S3 bucket (SSE-S3)
  modules/etl/         # SQS, Step Functions, ingestion Lambdas
  modules/query-api/   # /ask API Gateway + query Lambda
  modules/monitoring/  # dashboards, alarms, SNS
  bootstrap/           # CI/CD identity (OIDC provider + deploy role) + shared ECR repo
  prod/                # root stack composition (S3 backend, full stack)
scripts/               # repo + AWS state bucket + deploy-vars setup helpers
docs/                  # architecture and per-component docs
```

## Conventions

- **Timestamps:** ISO-8601 UTC with millisecond precision and a trailing `Z`
  (`backend/src/rag_aws/config/timestamps.py`).
- **Python:** 3.13, `ruff` (format + lint), `mypy --strict`, `pytest`.
- **Terraform:** `terraform fmt`; modules under `terraform/modules`, composed in
  `terraform/prod`.
- **Commits:** commitizen / conventional commits, with a co-author trailer.
