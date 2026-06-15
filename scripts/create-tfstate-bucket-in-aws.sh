#!/usr/bin/env bash
set -euo pipefail

# Creates the S3 bucket that holds Terraform's remote state. Locking is handled
# via S3-native lockfiles (`use_lockfile = true` in the backend block), so no
# DynamoDB table is needed. Run once per AWS account, before the first
# `terraform init`. Safe to re-run: AWS errors on already-existing resources are
# ignored.

PROJECT="rag-over-aws-docs"

# Single source of truth for the region: the aws_region variable default in the
# prod stack. Read it here so this bootstrap script never hardcodes its own copy.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="$(awk -F'"' '/variable "aws_region"/ {f=1} f && /default/ {print $2; exit}' "$SCRIPT_DIR/../terraform/prod/variables.tf")"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="${PROJECT}-tfstate-${ACCOUNT_ID}"

echo "Account: $ACCOUNT_ID"
echo "Region:  $REGION"
echo "Bucket:  $BUCKET"

aws s3api create-bucket --bucket "$BUCKET" --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION" \
  2>&1 | grep -v BucketAlreadyOwnedByYou || true

aws s3api put-bucket-versioning --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption --bucket "$BUCKET" \
  --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

aws s3api put-public-access-block --bucket "$BUCKET" \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "Done. Backend bucket=$BUCKET (S3-native locking)."
echo "Wire it into Terraform with, e.g.:"
echo "  terraform -chdir=terraform/prod init \\"
echo "    -backend-config=\"bucket=$BUCKET\" \\"
echo "    -backend-config=\"key=prod/terraform.tfstate\" \\"
echo "    -backend-config=\"region=$REGION\" \\"
echo "    -backend-config=\"use_lockfile=true\""
