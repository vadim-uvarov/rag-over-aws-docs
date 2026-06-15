#!/usr/bin/env bash
set -euo pipefail

# Sets the GitHub Actions variables the prod deploy needs (see
# .github/workflows/main.yml and deploy-manual.yml). They are stored on the
# `prod` GitHub Environment as plain variables, not secrets. Run from inside the
# repo with the gh CLI installed and authenticated (`gh auth login`).
#
# Note: the AWS region is NOT a GitHub variable. It is read from the aws_region
# variable default in terraform/prod/variables.tf (the single source of truth)
# by the deploy workflow itself.

ENVIRONMENT="prod"

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: the GitHub CLI (gh) is required. See https://cli.github.com/." >&2
  exit 1
fi

REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
echo "Repository:  $REPO"
echo "Environment: $ENVIRONMENT"
echo

# Prompt for each value. The region is intentionally not asked for here — it
# comes from terraform/prod/variables.tf (see the note at the top of this file).
read -r -p "AWS_ROLE_ARN (IAM role assumed via OIDC): " AWS_ROLE_ARN
read -r -p "TF_STATE_BUCKET (from scripts/create-tfstate-bucket-in-aws.sh): " TF_STATE_BUCKET

if [ -z "$AWS_ROLE_ARN" ] || [ -z "$TF_STATE_BUCKET" ]; then
  echo "Error: AWS_ROLE_ARN and TF_STATE_BUCKET must not be empty." >&2
  exit 1
fi

# Ensure the environment exists before setting variables on it.
gh api --method PUT "repos/${REPO}/environments/${ENVIRONMENT}" >/dev/null

gh variable set AWS_ROLE_ARN --env "$ENVIRONMENT" --body "$AWS_ROLE_ARN"
gh variable set TF_STATE_BUCKET --env "$ENVIRONMENT" --body "$TF_STATE_BUCKET"

echo
echo "Done. Variables on the '$ENVIRONMENT' environment of $REPO:"
gh variable list --env "$ENVIRONMENT"
