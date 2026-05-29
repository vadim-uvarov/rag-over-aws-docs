# rag-over-aws-docs

This project is a web app that allows you to chat with AI agent about AWS documentation. The agent uses RAG to query the raw AWS documentation stored in the backend.


## Project layout

TODO


## Project architecture

TODO


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

1. Create the state bucket once per AWS account: `./scripts/create-bucket-for-tfstate-in-aws.sh`
   (it prints the bucket name).
2. Create the GitHub OIDC provider and the deploy IAM role:
   `./scripts/setup-aim-oidc-and-aim-role-for-cicd-in-aws.sh` (it prints the role ARN).
3. Set the deploy variables on the `prod` GitHub Environment — run
   `./scripts/setup-deploy-vars-in-github.sh` (uses the `gh` CLI and prompts for each value), or set
   them manually:
   - `AWS_ROLE_ARN` — the role ARN from step 2 (assumed via GitHub OIDC by `aws-actions/configure-aws-credentials`)
   - `AWS_REGION` — same region as `aws_region`
   - `TF_STATE_BUCKET` — the bucket name from step 1

The deploy jobs request `id-token: write` for OIDC; no long-lived AWS keys are needed.