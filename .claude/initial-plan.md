# Initial Plan — RAG over AWS Documentation (Demo Web App)

> Living planning document. Each top-level **PR** section maps to one pull request.
> Build order is top-to-bottom; later PRs branch off earlier ones where noted.

---

## 1. Goal

A demo web app where a user asks questions about AWS documentation and an AI agent
answers using Retrieval-Augmented Generation (RAG) over the official `awsdocs`
markdown corpus. Backend on AWS (Python), IaC in Terraform, frontend served via
CloudFront.

---

## 2. Decisions Log

Locked-in decisions (from clarification round):

| Topic | Decision |
|---|---|
| Corpus scope | **Curated subset** of `awsdocs` repos (config-driven, can grow later) |
| API response delivery | **Synchronous JSON** (API Gateway → Lambda, single response) |
| RAG observability | **Langfuse Cloud** (free tier; keys via Secrets Manager) |
| API auth / abuse control | **Per-session DynamoDB quota + WAF per-IP rate limit + global daily cap + Bedrock budget alarm** *(recommended default — confirm before PR5)* |
| Per-session limit | **20 questions / session**, 24h TTL *(confirm before PR5)* |
| Embedding model | **Amazon Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`) — cheapest Bedrock embedding; 512-dim for cost/storage |
| Generation model | **Amazon Nova Micro** (`amazon.nova-micro-v1:0`) — cheapest Nova text model |
| Vector store | **LanceDB** on S3 |
| Region | **us-east-1** (broadest Bedrock model availability) |

### Challenges raised to the original spec (resolutions baked into this plan)

1. **Cosine threshold was inverted.** Spec said "keep chunks with cosine *distance* > 0.7,"
   but larger distance = less similar. Implemented as **cosine similarity ≥ 0.7
   (distance ≤ 0.3)**. Retrieval: top-20 → keep similarity ≥ 0.7 → top-5 → if empty,
   answer `"I don't know the answer"`.
2. **Standalone "tokenize" Step Functions state dropped.** Embedding models tokenize
   internally; a tokenizer is only needed *during chunking* to measure chunk size.
   Token counting is kept as a swappable concern **inside the chunk stage**, not a
   separate persisted state. Pipeline states: **chunk → embed → index**.
   - Caveat: Nova's exact tokenizer is not publicly exposed via LlamaIndex. We use a
     documented tokenizer proxy (tiktoken `cl100k_base`) purely for chunk-size budgeting
     and note this in code/docs.
3. **Per-file Step Functions executions don't scale for the initial backfill.** A first
   ingest is thousands of objects. Use **EventBridge → SQS (buffer) → batched Step
   Functions execution** (Map state over a batch), with DLQ + retries. Initial backfill
   runs as a controlled batch, not thousands of concurrent executions.

### Open items to confirm before the relevant PR
- Auth approach + per-session limit value (needed for PR5).
- Final list of curated `awsdocs` repos (needed for PR2). Proposed starter set:
  `amazon-s3-userguide`, `aws-lambda-developer-guide`, `iam-user-guide`,
  `amazon-ec2-user-guide`, `aws-cli-user-guide` (adjust freely).

---

## 3. Architecture

```
                         ┌─────────────────────── INGESTION (local for now) ───────────────────────┐
   awsdocs GitHub  ──►   clone curated repos ──► extract .md ──► S3  corpus/raw/ (A)
                         (writes manifest with content hashes to corpus/manifests/ (D))
                                                        │
                                    S3 ObjectCreated/Removed events
                                                        ▼
   EventBridge rule ──► SQS (buffer, batch) ──► Dispatcher ──► Step Functions (Map over batch)
                                                                  │  chunk  → S3 corpus/chunks/ (B)
                                                                  │  embed  → Titan v2 (Bedrock)
                                                                  └  index  → LanceDB @ S3 corpus/vector-store/ (C)

                         ┌──────────────────────────── QUERY (synchronous) ───────────────────────┐
   CloudFront ──► S3 web/ (React SPA)
        │
        └─► API Gateway (WAF + usage plan) ──► Query Lambda (container image)
                                                   ├─ session quota check (DynamoDB)
                                                   ├─ embed query (Titan v2)
                                                   ├─ LanceDB search: top20 → sim≥0.7 → top5
                                                   ├─ generate (Nova Micro via LangChain)
                                                   ├─ trace to Langfuse Cloud
                                                   └─ return JSON { answer, chunks[] }
```

---

## 4. Single S3 Bucket — Prefix Layout (placeholders A/B/C/D)

One project bucket (versioned, SSE-KMS, public access blocked):

| Placeholder | Prefix | Contents |
|---|---|---|
| **A** | `corpus/raw/` | Raw AWS markdown docs, mirrored from curated repos. Key = `<repo>/<path>.md` |
| **B** | `corpus/chunks/` | Plain-text chunks. Key = `<repo>/<doc-path>/<chunk-index>.txt` |
| **C** | `corpus/vector-store/` | LanceDB table(s) — embeddings + chunk metadata |
| **D** | `corpus/manifests/` | Ingestion state: per-file content hashes + chunk inventory (drives incremental add/update/delete) |
| — | `web/` | Frontend build artifacts (CloudFront origin) |

---

## 5. Tech Stack

- **Frontend:** React + TypeScript + Vite, Vitest + React Testing Library (unit/component),
  Playwright (smoke e2e). Hosted on S3 + CloudFront (OAC, cache invalidation on deploy).
- **Backend:** Python 3.12, AWS Lambda (container images where deps are heavy — LanceDB/pyarrow),
  API Gateway (REST), Step Functions, EventBridge, SQS, DynamoDB, Bedrock.
- **RAG libs:** LlamaIndex (chunking), LangChain (generation), LanceDB (vector store),
  Langfuse (tracing).
- **IaC:** Terraform (remote state in S3 + DynamoDB lock). `terraform fmt`/`validate` in CI.
- **Python tooling:** `ruff` (format+lint), `mypy` (types), `pytest` (+ `moto`/`localstack`
  for AWS integration tests). `pre-commit`.

### Repo layout
```
backend/
  src/rag_aws/
    config/            # settings, model ids, env loading
    ingestion/         # local corpus sync script + lib
    etl/
      interfaces.py    # Chunker, Embedder, VectorIndex, TokenCounter (ABCs)
      chunking/        # LlamaIndex naive chunker
      embedding/       # Bedrock Titan v2 embedder
      indexing/        # LanceDB index
      handlers/        # Lambda entrypoints for SF states
    query/
      retriever.py     # embed query, search, filter, top-k, fallback
      generator.py     # LangChain + Nova Micro, prompt template
      tracing.py       # Langfuse
      handler.py       # API Lambda entrypoint, session quota
  tests/
    unit/  integration/
frontend/
  src/  tests/
infra/
  modules/             # storage, etl, query-api, frontend-hosting, monitoring
  envs/dev/            # root module composition + backend config
scripts/               # helper scripts (local backfill, deploy)
docs/                  # architecture.md, ingestion.md, etl.md, rag.md, api.md, frontend.md, monitoring.md
```

---

## 6. PR-by-PR Plan

> Each PR: branch off `main` unless it must build on an unmerged PR (then branch off
> that PR's branch and target it, per CLAUDE.md). Every PR keeps `readme.md`/`docs/`
> current and is green on lint + type + tests in CI.

### PR1 — Foundations: tooling, CI, Terraform skeleton, project bucket
**Depends on:** none (branch off `main`).
**Goal:** Everything later PRs stand on.
- Monorepo layout above; finalize `pyproject.toml` (ruff, mypy, pytest config), `pre-commit`.
- Terraform bootstrap: remote state (S3 + DynamoDB lock), provider, **naming + tagging
  conventions**, `dev` env composition.
- `infra/modules/storage`: the **project S3 bucket** (versioning, SSE-KMS, block public
  access, lifecycle for noncurrent versions) + the A/B/C/D + `web/` prefixes documented.
- Config module: ISO-8601 UTC millisecond `Z` timestamp helper (project convention),
  central model-id/env settings.
- CI workflows: python (ruff/mypy/pytest), terraform (fmt/validate), frontend build stub.
- **Tests:** unit — config loader, timestamp formatter (border cases: ms padding, UTC).
  Smoke — `terraform validate` in CI.
- **Docs:** `readme.md` overview, `docs/architecture.md` (diagram + data flow + S3 layout).
- **Acceptance:** CI green; `terraform plan` for storage succeeds; bucket provisioned in dev.

### PR2 — Local corpus ingestion (GitHub → S3 folder A)
**Depends on:** PR1.
**Goal:** Populate `corpus/raw/` (A) and the manifest (D), runnable locally.
- Python script `scripts/ingest_corpus.py` + lib in `ingestion/`:
  - Config-driven list of curated `awsdocs` repos.
  - Clone/pull (shallow), select `.md` files, map to S3 keys `<repo>/<path>.md`.
  - **Incremental sync:** compute per-file content hash; compare to manifest (D);
    upload added/changed, delete removed; rewrite manifest. ISO-8601 UTC `Z` timestamps.
  - Idempotent + re-runnable; `--dry-run`.
- **Tests:**
  - Unit — repo/file filtering, key mapping, hash-diff (add/update/remove/no-op border cases),
    manifest read/write. Smoke test for the top-level sync function.
  - Integration — full sync against `moto`/`localstack` S3 with a tiny fixture repo.
- **Docs:** `docs/ingestion.md` (how to run, repo config, manifest format).
- **Acceptance:** Running locally mirrors curated docs into A and writes a correct manifest;
  re-run is a no-op; deleting a source file removes it from A.

### PR3 — ETL stage libraries + swappable abstractions (no infra)
**Depends on:** PR1 (parallel with PR2).
**Goal:** Pure, unit-testable chunk/embed/index logic behind interfaces.
- `etl/interfaces.py`: `Chunker`, `TokenCounter`, `Embedder`, `VectorIndex` ABCs
  (clear contracts so implementations swap freely).
- Implementations:
  - `chunking/`: LlamaIndex **naive** chunker; uses `TokenCounter` (tiktoken proxy) for
    size budgeting; writes chunk text to B (`<repo>/<doc>/<idx>.txt`) with metadata
    (source doc, repo, chunk index, char span).
  - `embedding/`: Bedrock **Titan v2** embedder (512-dim), batched, with retry/backoff.
  - `indexing/`: **LanceDB** index over C — upsert by chunk id, delete-by-document
    (for updates/removals), schema = {id, vector, text, source_doc, repo, chunk_index, ts}.
- **Tests:**
  - Unit per stage (fakes for Bedrock/LanceDB): chunk boundaries, empty/tiny/huge doc
    border cases, embedder batching + retry, index upsert/delete/idempotency.
  - **Contract tests** run against every implementation of each interface.
  - Integration — chunk→embed→index wired with `moto` S3 + a local LanceDB on a sample doc.
- **Docs:** `docs/etl.md` (interfaces, how to swap an implementation).
- **Acceptance:** A sample doc flows chunk→embed→index locally; coverage on stage logic.

### PR4 — ETL orchestration infra (EventBridge → SQS → Step Functions)
**Depends on:** PR2 + PR3 (branch off whichever merges last; otherwise stack).
**Goal:** Automated, batched, resilient processing of changed files.
- Lambda handlers in `etl/handlers/` wrapping PR3 stage libs (container images for
  LanceDB/pyarrow weight).
- **Step Functions** state machine: `Map(batch) → chunk → embed → index`, with
  per-state retry/catch and run-level error handling.
- **EventBridge** rule on S3 `ObjectCreated`/`ObjectRemoved` for prefix A → **SQS** buffer
  → dispatcher (Lambda or EventBridge Pipes) that batches messages and `StartExecution`.
- **DLQ** on SQS + failed-execution alarm hook (wired fully in PR7).
- **Backfill path:** `scripts/backfill.py` enqueues all of A in controlled batches for the
  first bulk load (avoids thousands of concurrent executions / Bedrock throttling).
- Terraform `infra/modules/etl`.
- **Tests:**
  - Unit — each handler (event parsing, error mapping), dispatcher batching logic.
  - Integration — state machine via **Step Functions Local** + `moto`/`localstack` on a
    small batch (smoke: changed file ends up indexed in C; removed file deleted from C).
- **Docs:** update `docs/etl.md` (orchestration, backfill, retries/DLQ).
- **Acceptance:** Putting/removing a file in A drives an indexed/removed vector in C;
  backfill processes the curated corpus without throttling failures.

### PR5 — RAG query backend (retrieval + generation + API)
**Depends on:** PR3 (libs) + PR4 (a populated index). Confirm auth decision first.
**Goal:** Synchronous `/ask` endpoint returning answer + chunks.
- `query/retriever.py`: embed query (Titan v2) → LanceDB **top-20** → keep
  **cosine similarity ≥ 0.7** → **top-5** → if empty signal fallback.
- `query/generator.py`: **LangChain + Nova Micro**; prompt template injects retrieved
  chunks; empty-context path returns exactly `"I don't know the answer"`.
- `query/tracing.py`: **Langfuse Cloud** tracing (query, retrieved chunks + scores,
  generation); keys from Secrets Manager.
- `query/handler.py`: API Lambda (container image). Returns
  `{ "answer": str, "chunks": [{ "source_doc", "link", "cosine_distance" }], "session": {...} }`,
  sorted by **descending relevance**.
- **Abuse controls:** **DynamoDB per-session counter** (24h TTL, 20/session) → `429` when
  exceeded; **API Gateway usage plan** global daily cap; **WAF** per-IP rate rule;
  **AWS Budgets** alarm on Bedrock spend → SNS.
- Terraform `infra/modules/query-api` (API Gateway, Lambda, DynamoDB, WAF, usage plan, Secrets).
- **Tests:**
  - Unit — retrieval filter (boundary cases at exactly 0.7, fewer than 5, zero survivors →
    fallback), prompt assembly, response shaping/sorting, session-quota logic
    (under/at/over limit, TTL reset).
  - Integration — handler end-to-end with mocked Bedrock + real local LanceDB fixture
    (smoke: known question returns expected chunk; nonsense question returns "I don't know").
- **Docs:** `docs/rag.md` (retrieval strategy, prompt), `docs/api.md` (request/response, errors).
- **Acceptance:** `/ask` returns grounded answers + ranked chunks; over-limit returns 429;
  Langfuse shows traces.

### PR6 — Frontend (React SPA) + CloudFront hosting
**Depends on:** PR5 (API contract).
**Goal:** The described UI.
- React + TS + Vite SPA:
  - Text input + "Ask" button. On submit: clear+disable input, echo the prompt as text
    below, show a **"thinking…" spinner**.
  - On response: render the answer below the prompt; below it, list **retrieved chunks**
    in **descending relevance**, each with parent-doc name/link + cosine distance.
  - Session handling (store/send session id), graceful `429` ("session limit reached") and
    error states.
- Terraform `infra/modules/frontend-hosting`: S3 `web/` origin, CloudFront (OAC, SPA error
  routing, TLS), deploy + invalidation in CI.
- **Tests:**
  - Component (Vitest + RTL): submit flow disables input + shows spinner; renders answer +
    sorted chunks; "I don't know" path; 429 path.
  - Smoke e2e (Playwright) against a mocked API.
- **Docs:** `docs/frontend.md` (run/build/deploy, env config).
- **Acceptance:** Deployed via CloudFront; full happy path + limit/error paths work against PR5.

### PR7 — Monitoring, alarms & observability
**Depends on:** PR4 + PR5 + PR6 (the resources to monitor).
**Goal:** Operational visibility + cost safety.
- CloudWatch: structured JSON logging across Lambdas (log-group retention), **dashboards**
  (Lambda errors/duration/throttles, Step Functions failed executions, API 4xx/5xx + latency,
  Bedrock throttles, SQS depth/DLQ).
- **Alarms → SNS:** SF failures, DLQ not-empty, API 5xx spike, Bedrock throttling,
  **AWS Budgets** Bedrock cost (if not added in PR5).
- **X-Ray** tracing across API → Lambda; confirm **Langfuse** dashboards for RAG quality.
- Optional CloudWatch Synthetics canary on `/ask`.
- Terraform `infra/modules/monitoring`.
- **Tests:** unit for any log/metric helper; integration smoke that a forced error emits the
  expected metric/alarm state (where feasible with `moto`).
- **Docs:** `docs/monitoring.md` (dashboards, alarms, **runbook** for common failures).
- **Acceptance:** Dashboards populated; a simulated failure trips the right alarm; budget alarm armed.

### PR8 (optional / later) — Automate periodic ingestion
**Depends on:** PR2.
**Goal:** Replace the local ingestion run with a scheduled AWS job.
- Containerize the PR2 ingestion lib; run on **EventBridge Scheduler → Fargate task** (or
  Lambda if it fits limits); same incremental manifest logic feeds the existing ETL trigger.
- Terraform + schedule; alarm on failed runs.
- **Tests:** reuse PR2 suite; integration smoke of the scheduled task.
- **Docs:** update `docs/ingestion.md`.
- **Acceptance:** Corpus refreshes on schedule and changed files flow through ETL automatically.

---

## 7. Cross-Cutting Concerns

- **Testing strategy:** unit tests for all non-trivial logic (branches + border cases per
  CLAUDE.md), at least one smoke test per module, integration tests with `moto`/`localstack`/
  Step Functions Local. CI gates merges on lint + type + tests.
- **Security:** least-privilege IAM per Lambda/role; SSE-KMS on the bucket; block public
  access (CloudFront via OAC only); secrets in Secrets Manager; WAF on the API.
- **Cost control:** cheapest Bedrock models; 512-dim embeddings; batched embedding;
  per-session + global request caps; Bedrock budget alarm; S3 lifecycle on old versions.
- **Conventions:** commitizen commits + co-author; verbs-first function names; Google-style
  docstrings; ISO-8601 UTC ms `Z` timestamps; `terraform fmt`; keep docs current before each PR.

---

## 8. Build Order Summary

```
PR1 ─┬─► PR2 ─┐
     └─► PR3 ─┴─► PR4 ─► PR5 ─► PR6 ─► PR7
                                  PR2 ─► PR8 (optional)
```
PR2 and PR3 can be developed in parallel after PR1.
