# Architecture

RAG-over-AWS-docs is a demo web app: a user asks a question about AWS
documentation and an AI agent answers using Retrieval-Augmented Generation (RAG)
over the official `awsdocs` markdown corpus.

> This document tracks the target architecture. It is built out PR-by-PR; see
> `.claude/initial-plan.md` for the full plan. PR1 (this PR) delivers the
> foundations: tooling, CI, the Terraform skeleton, and the project S3 bucket.

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

One project bucket (versioned, SSE-KMS, all public access blocked):

| Placeholder | Prefix | Contents |
|---|---|---|
| **A** | `corpus/raw/` | Raw AWS markdown, key = `<repo>/<path>.md` |
| **B** | `corpus/chunks/` | Plain-text chunks, key = `<repo>/<doc>/<chunk-index>.txt` |
| **C** | `corpus/vector-store/` | LanceDB table(s): embeddings + chunk metadata |
| **D** | `corpus/manifests/` | Ingestion state: per-file content hashes + chunk inventory |
| — | `web/` | Frontend build artifacts (CloudFront origin) |

The bucket and its KMS key are provisioned by `terraform/modules/storage`,
composed in `terraform/prod`.

## Key decisions

| Topic | Decision |
|---|---|
| Region | **eu-west-1** (matches existing Terraform backend + CI/OIDC setup) |
| Embedding model | **Amazon Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`), 512-dim |
| Generation model | **Amazon Nova Micro** (`amazon.nova-micro-v1:0`) |
| Vector store | **LanceDB** on S3 |
| API delivery | Synchronous JSON (API Gateway → Lambda) |
| Observability | Langfuse Cloud (keys via Secrets Manager) |

> **Bedrock availability risk (to verify before PR5):** Amazon Nova models and
> Titan Embeddings V2 must be confirmed available in **eu-west-1**. If a model is
> not offered there, the fallback is a cross-region inference profile or an
> equivalent model available in the region. This is the one decision carried
> forward from PR1 that needs validation.

## Repository layout

```
backend/src/rag_aws/   # Python backend package
  config/              # settings, model ids, timestamp helper
tests/
  unit/  integration/
frontend/              # React SPA (stub in PR1, built in PR6)
terraform/
  modules/storage/     # project S3 bucket + KMS
  prod/                # root stack composition (S3 backend, OIDC deploy)
scripts/               # repo + AWS + CI/CD setup helpers
docs/                  # architecture and per-component docs
```

## Conventions

- **Timestamps:** ISO-8601 UTC with millisecond precision and a trailing `Z`
  (`backend/src/rag_aws/config/timestamps.py`).
- **Python:** 3.13, `ruff` (format + lint), `mypy --strict`, `pytest`.
- **Terraform:** `terraform fmt`; modules under `terraform/modules`, composed in
  `terraform/prod`.
- **Commits:** commitizen / conventional commits, with a co-author trailer.
