#!/usr/bin/env bash
set -euo pipefail

# Sets up GitHub Actions -> AWS OIDC federation for the prod deploy:
#   1. Creates the IAM OIDC identity provider for token.actions.githubusercontent.com,
#      if it doesn't already exist.
#   2. Creates the IAM role the CI/CD workflows assume, if it doesn't already exist,
#      trusting that provider and scoped to this repo's `prod` environment.
# The printed role ARN is what you set as AWS_ROLE_ARN on the prod GitHub
# Environment (see scripts/setup-deploy-vars-in-github.sh). Requires the AWS CLI,
# authenticated with permissions to manage IAM.

OIDC_HOST="token.actions.githubusercontent.com"
AUDIENCE="sts.amazonaws.com"
ENVIRONMENT="prod"
ROLE_NAME="rag-over-aws-docs-cicd-deploy"

if ! command -v aws >/dev/null 2>&1; then
  echo "Error: the AWS CLI is required." >&2
  exit 1
fi

# Determine the GitHub repo (owner/name) used to scope the role's trust policy.
DEFAULT_REPO=""
if command -v gh >/dev/null 2>&1; then
  DEFAULT_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
fi
read -r -p "GitHub repository (owner/name)${DEFAULT_REPO:+ [$DEFAULT_REPO]}: " REPO
REPO="${REPO:-$DEFAULT_REPO}"
if [ -z "$REPO" ]; then
  echo "Error: repository is required (owner/name)." >&2
  exit 1
fi

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_HOST}"
BUCKET="rag-over-aws-docs-tfstate-${ACCOUNT_ID}"
# The project bucket Terraform creates/manages (see terraform/prod/main.tf). Must
# stay in sync with the bucket_name local there: project-environment-accountid.
PROJECT_BUCKET="rag-over-aws-docs-${ENVIRONMENT}-${ACCOUNT_ID}"

echo "Account:     $ACCOUNT_ID"
echo "Repository:  $REPO"
echo "Role:        $ROLE_NAME"
echo "Environment: $ENVIRONMENT"
echo

# 1. OIDC identity provider ----------------------------------------------------
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$PROVIDER_ARN" >/dev/null 2>&1; then
  echo "OIDC provider already exists: $PROVIDER_ARN"
else
  # AWS no longer uses the thumbprint for this well-known provider, but the API
  # still requires one; derive it from the live certificate.
  THUMBPRINT="$(echo | openssl s_client -servername "$OIDC_HOST" -connect "${OIDC_HOST}:443" 2>/dev/null \
    | openssl x509 -fingerprint -sha1 -noout | cut -d= -f2 | tr -d ':' | tr '[:upper:]' '[:lower:]')"
  aws iam create-open-id-connect-provider \
    --url "https://${OIDC_HOST}" \
    --client-id-list "$AUDIENCE" \
    --thumbprint-list "$THUMBPRINT" >/dev/null
  echo "Created OIDC provider: $PROVIDER_ARN"
fi

# 2. IAM role ------------------------------------------------------------------
TRUST_POLICY="$(mktemp)"
cat >"$TRUST_POLICY" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": { "Federated": "${PROVIDER_ARN}" },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": { "${OIDC_HOST}:aud": "${AUDIENCE}" },
        "StringLike": { "${OIDC_HOST}:sub": "repo:${REPO}:environment:${ENVIRONMENT}" }
      }
    }
  ]
}
JSON

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "Role already exists: $ROLE_NAME (refreshing trust policy)"
  aws iam update-assume-role-policy --role-name "$ROLE_NAME" \
    --policy-document "file://${TRUST_POLICY}" >/dev/null
else
  aws iam create-role --role-name "$ROLE_NAME" \
    --description "GitHub Actions CI/CD deploy for ${REPO} (${ENVIRONMENT})" \
    --assume-role-policy-document "file://${TRUST_POLICY}" >/dev/null
  echo "Created role: $ROLE_NAME"
fi

# Permissions, in three groups:
#   1. Terraform state bucket (init/plan/apply + S3-native locking).
#   2. The project S3 bucket Terraform creates and manages. Terraform reads back
#      every bucket sub-resource (versioning, encryption, lifecycle, public
#      access block, tagging, ...) on each apply, so the role needs the matching
#      Get*/Put* actions, not just CreateBucket. s3:*Bucket* covers them and any
#      bucket settings added by future modules without re-editing this policy.
#   3. The customer-managed KMS key that encrypts the project bucket. CreateKey
#      and ListAliases cannot be scoped to a key ARN (the key/aliases are not
#      addressable at create time), so KMS actions use Resource "*"; access to
#      existing keys is still gated by each key's own key policy.
# Add further statements for any new infrastructure you deploy.
PERMISSIONS_POLICY="$(mktemp)"
cat >"$PERMISSIONS_POLICY" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TerraformStateBucket",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::${BUCKET}"
    },
    {
      "Sid": "TerraformStateObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::${BUCKET}/*"
    },
    {
      "Sid": "ProjectBucket",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:ListBucket",
        "s3:GetBucket*",
        "s3:PutBucket*",
        "s3:GetEncryptionConfiguration",
        "s3:PutEncryptionConfiguration",
        "s3:GetLifecycleConfiguration",
        "s3:PutLifecycleConfiguration",
        "s3:GetAccelerateConfiguration",
        "s3:GetReplicationConfiguration",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::${PROJECT_BUCKET}",
        "arn:aws:s3:::${PROJECT_BUCKET}/*"
      ]
    },
    {
      "Sid": "ProjectBucketKmsKey",
      "Effect": "Allow",
      "Action": [
        "kms:CreateKey",
        "kms:DescribeKey",
        "kms:ListAliases",
        "kms:CreateAlias",
        "kms:DeleteAlias",
        "kms:UpdateAlias",
        "kms:GetKeyPolicy",
        "kms:PutKeyPolicy",
        "kms:GetKeyRotationStatus",
        "kms:EnableKeyRotation",
        "kms:DisableKeyRotation",
        "kms:ListResourceTags",
        "kms:TagResource",
        "kms:UntagResource",
        "kms:ScheduleKeyDeletion",
        "kms:CancelKeyDeletion"
      ],
      "Resource": "*"
    }
  ]
}
JSON
aws iam put-role-policy --role-name "$ROLE_NAME" \
  --policy-name terraform-state --policy-document "file://${PERMISSIONS_POLICY}" >/dev/null

rm -f "$TRUST_POLICY" "$PERMISSIONS_POLICY"

ROLE_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query Role.Arn --output text)"
echo
echo "Done. Role ARN:"
echo "  $ROLE_ARN"
echo "Set it as AWS_ROLE_ARN on the '${ENVIRONMENT}' GitHub Environment"
echo "(e.g. run scripts/setup-deploy-vars-in-github.sh)."
