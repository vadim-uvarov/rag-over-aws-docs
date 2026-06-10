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
  modules/storage/     # project S3 bucket + KMS key
  bootstrap/           # one-time CI/CD identity: GitHub OIDC provider + deploy role
  prod/                # root stack composition (S3 remote state, project bucket)
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


## Local dev and deploy instructions

### Local dev
```sh
make install   # uv sync
make hooks     # install git hooks
make lint test
```

### Local deploy

TODO


## Setting up the github repo and CI/CD

### Github repo setup (branch protection and PR rules)

Once the repo is on GitHub with a `main` branch, run `./scripts/setup-github-repo.sh` (needs
the `gh` CLI with admin rights). It protects `main` so it can only be updated via a pull
request whose pipeline passes and whose conversations are all resolved.

### Deploy setup (AWS and Github Actions)

The `prod` stack uses an S3 backend with S3-native locking. The bucket name embeds the AWS
account ID, so it is passed at `terraform init` time rather than hardcoded.

1. Create the state bucket once per AWS account: `./scripts/create-tfstate-bucket-in-aws.sh`
   (it prints the bucket name).
2. Create the GitHub OIDC provider and the deploy IAM role by applying the
   [`bootstrap`](terraform/bootstrap) stack (run once, with admin AWS credentials) —
   see [`terraform/bootstrap/README.md`](terraform/bootstrap/README.md). Read the role
   ARN with `terraform -chdir=terraform/bootstrap output -raw deploy_role_arn`.
3. Set the deploy variables on the `prod` GitHub Environment — run
   `./scripts/setup-deploy-vars-in-github.sh` (uses the `gh` CLI and prompts for each value), or set
   them manually:
   - `AWS_ROLE_ARN` — the role ARN from step 2 (assumed via GitHub OIDC by `aws-actions/configure-aws-credentials`)
   - `AWS_REGION` — same region as `aws_region`
   - `TF_STATE_BUCKET` — the bucket name from step 1

The deploy jobs request `id-token: write` for OIDC; no long-lived AWS keys are needed.