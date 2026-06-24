# rag-over-aws-docs

This project is a web app that allows you to chat with AI agent about AWS documentation. The agent uses RAG to query the raw AWS documentation stored in the backend.


## Project layout

```
backend/src/rag_aws/   # Python backend package (config in PR1; ETL/query later)
  config/              # central settings, Bedrock model ids, timestamp helper
tests/
  unit/  integration/  # pytest suites
frontend/              # React SPA (build stub in PR1, full app in PR6)
terraform/
  modules/storage/     # project S3 bucket (SSE-S3)
  modules/etl/         # ingestion ETL: SQS, Step Functions, Lambdas
  modules/query-api/   # synchronous /ask API Gateway + query Lambda
  modules/monitoring/  # dashboards, alarms, SNS topic
  bootstrap/           # one-time CI/CD identity: OIDC provider, deploy role, shared ECR repo
  prod/                # root stack composition (S3 remote state, full stack)
scripts/               # GitHub repo, AWS state bucket, and deploy-vars setup helpers
docs/                  # architecture.md and per-component docs
```


## Project architecture

A user asks a question in the SPA; an API Lambda embeds the query, retrieves the
most similar documentation chunks from a LanceDB vector store on S3, and has a
Bedrock model generate a grounded answer. Documentation is ingested from the
`awsdocs` GitHub repos into S3 and processed (chunk → embed → index) by an
event-driven ETL pipeline.

See [`docs/architecture.md`](docs/architecture.md) for the full data flow, the
single-bucket prefix layout, and key technology decisions. The project is built
incrementally per [`.claude/initial-plan.md`](.claude/initial-plan.md).


## Documentation

- [`docs/architecture.md`](docs/architecture.md) — data flow, S3 layout, decisions
- [`docs/ingestion.md`](docs/ingestion.md) — mirroring AWS docs into the corpus bucket
- [`docs/etl.md`](docs/etl.md) — chunk → embed → index stages and interfaces
- [`docs/rag.md`](docs/rag.md) — retrieval strategy, prompt, abuse/cost controls
- [`docs/api.md`](docs/api.md) — `/ask` request/response and errors
- [`docs/frontend.md`](docs/frontend.md) — SPA UX, run/build/deploy, tests
- [`docs/monitoring.md`](docs/monitoring.md) — dashboards, alarms, X-Ray, runbook
- [`docs/costs.md`](docs/costs.md) — fixed vs usage cost model and levers to cut the bill


## Local dev and deploy instructions

### Local dev
```sh
make install   # uv sync
make hooks     # install git hooks
make lint test
```

### Local deploy

The Terraform module enable flags (`enable_etl`, `enable_query_api`,
`enable_monitoring`) default to `false`, so a plain local `terraform apply` of
`prod` brings up only `storage` + `frontend` and `terraform validate` / PR plans
stay green without a container image. The CI/CD pipeline overrides these flags to
deploy the full stack (see below).


## Setting up the github repo and CI/CD

### Github repo setup (branch protection and PR rules)

Once the repo is on GitHub with a `main` branch, run `./scripts/setup-repo-and-infra/setup-github-repo.sh` (needs
the `gh` CLI with admin rights). It protects `main` so it can only be updated via a pull
request whose pipeline passes and whose conversations are all resolved.

### Deploy setup (AWS and Github Actions)

The `prod` stack uses an S3 backend with S3-native locking. The bucket name embeds the AWS
account ID, so it is passed at `terraform init` time rather than hardcoded.

1. Create the state bucket once per AWS account: `./scripts/setup-repo-and-infra/create-tfstate-bucket-in-aws.sh`
   (it prints the bucket name).
2. Create the GitHub OIDC provider, the deploy IAM role, and the shared `rag-aws-etl`
   ECR repository by applying the [`bootstrap`](terraform/bootstrap) stack (run once,
   with admin AWS credentials) — see
   [`terraform/bootstrap/README.md`](terraform/bootstrap/README.md). Read the role
   ARN with `terraform -chdir=terraform/bootstrap output -raw deploy_role_arn`.
3. Set the deploy variables on the `prod` GitHub Environment — run
   `./scripts/setup-repo-and-infra/setup-deploy-vars-in-github.sh` (uses the `gh` CLI and prompts for each value), or set
   them manually:
   - `AWS_ROLE_ARN` — the role ARN from step 2 (assumed via GitHub OIDC by `aws-actions/configure-aws-credentials`)
   - `TF_STATE_BUCKET` — the bucket name from step 1

The AWS region is **not** a GitHub variable: it is defined once in
[`config/deploy.json`](config/deploy.json), the single source of truth read by both
Terraform stacks (`jsondecode`) and the deploy workflow (`jq`, for the AWS
credentials, ECR, and the Terraform backend region). Change the region in that one
file.

The deploy jobs request `id-token: write` for OIDC; no long-lived AWS keys are needed.

### What the prod pipeline deploys

The prod deploy workflow ([`reusable-deploy-prod.yml`](.github/workflows/reusable-deploy-prod.yml))
brings up the **full stack** — `storage`, `frontend`, ETL, query API, and monitoring.
On each deploy it:

1. Logs into ECR and builds the shared Lambda container image from
   [`backend/Dockerfile`](backend/Dockerfile), tagging it with the deployed commit's
   short SHA and pushing it to the `rag-aws-etl` repository (idempotent — a rerun on
   the same commit is a no-op). One image backs all three Lambdas (ETL process, ETL
   dispatch, and the query API); the handler is selected per function via
   `image_config.command`.
2. Runs `terraform apply` on `prod` with the module enable flags turned on:
   `enable_etl=true`, `enable_query_api=true`, `enable_monitoring=true`, and
   `enable_frontend=true`, passing the freshly pushed image URI to both the ETL and
   query-API Lambdas. The Terraform variable defaults stay `false` (so local applies
   and PR plans are unaffected) — enablement happens only through these workflow
   `-var` overrides.

`alarm_email` is left unset, so the monitoring SNS topic is created without an email
subscription; subscribe an address there if you want alarm notifications.

### Prerequisites for the first prod deploy

> **The bootstrap stack must be applied manually, out-of-band, BEFORE the first prod
> deploy.** It creates the `rag-aws-etl` ECR repository and grants the IAM
> permissions the prod apply depends on (ECR push, Lambda, IAM/PassRole, SQS, Step
> Functions, EventBridge, CloudWatch Logs/alarms/dashboards, API Gateway, DynamoDB,
> SNS, Secrets Manager, Budgets). If it is not applied first, the docker push
> fails (repository missing) and `terraform apply` fails with `AccessDenied`. Apply
> it per [`terraform/bootstrap/README.md`](terraform/bootstrap/README.md).

> **Verify Bedrock model availability in `eu-west-1`** before the first deploy:
> `amazon.titan-embed-text-v2:0` (embeddings) and `amazon.nova-micro-v1:0`
> (generation), with model access enabled in the account. If only cross-region
> **inference profiles** are available in the region, switch the model IDs to their
> profile IDs (e.g. `eu.amazon.*`) in
> [`backend/src/rag_aws/config/settings.py`](backend/src/rag_aws/config/settings.py),
> and widen the ETL process role's Bedrock statement in
> [`terraform/modules/etl/iam.tf`](terraform/modules/etl/iam.tf) to also allow the
> `inference-profile/*` ARN (the query-API role already allows it).