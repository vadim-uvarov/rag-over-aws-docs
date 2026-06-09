terraform {
  required_version = ">= 1.5"

  # Bootstrap state lives in the same bucket as the prod stack, under a separate
  # key. The bucket is created out-of-band (scripts/create-tfstate-bucket-in-aws.sh)
  # because it must exist before any Terraform runs. The bucket name embeds the
  # account ID, so it is supplied at init time rather than hardcoded here.
  backend "s3" {
    key          = "bootstrap/terraform.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

# The deploying account; used to build the state and project bucket names that
# the deploy role is scoped to.
data "aws_caller_identity" "current" {}

locals {
  project     = "rag-over-aws-docs"
  environment = var.environment
  oidc_host   = "token.actions.githubusercontent.com"

  common_tags = {
    Project     = local.project
    Environment = local.environment
    ManagedBy   = "terraform"
  }

  # Bucket names must stay in sync with scripts/create-tfstate-bucket-in-aws.sh
  # and terraform/prod (project-environment-accountid).
  tfstate_bucket = "${local.project}-tfstate-${data.aws_caller_identity.current.account_id}"
  project_bucket = "${local.project}-${local.environment}-${data.aws_caller_identity.current.account_id}"
}

# GitHub Actions OIDC identity provider. AWS no longer validates the thumbprint
# for this well-known issuer, so thumbprint_list is intentionally omitted and
# left to the provider's computed default.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://${local.oidc_host}"
  client_id_list = ["sts.amazonaws.com"]
}

# Trust policy: only GitHub Actions runs for this repo's `prod` environment may
# assume the role, via OIDC (no long-lived AWS keys).
data "aws_iam_policy_document" "cicd_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_host}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "${local.oidc_host}:sub"
      values   = ["repo:${var.github_repo}:environment:${local.environment}"]
    }
  }
}

resource "aws_iam_role" "cicd_deploy" {
  name               = "${local.project}-cicd-deploy"
  description        = "GitHub Actions CI/CD deploy for ${var.github_repo} (${local.environment})"
  assume_role_policy = data.aws_iam_policy_document.cicd_trust.json
}

# Permissions, in three groups:
#   1. Terraform state bucket (init/plan/apply + S3-native locking).
#   2. The project S3 bucket the prod stack creates and manages. Terraform reads
#      back every bucket sub-resource (versioning, encryption, lifecycle, public
#      access block, tagging, ...) on each apply, so the role needs the matching
#      Get*/Put* actions, not just CreateBucket.
#   3. The customer-managed KMS key that encrypts the project bucket. CreateKey
#      and ListAliases cannot be scoped to a key ARN (the key/aliases are not
#      addressable at create time), so KMS actions use "*"; access to existing
#      keys is still gated by each key's own key policy.
data "aws_iam_policy_document" "cicd_permissions" {
  statement {
    sid       = "TerraformStateBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = ["arn:aws:s3:::${local.tfstate_bucket}"]
  }

  statement {
    sid       = "TerraformStateObjects"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["arn:aws:s3:::${local.tfstate_bucket}/*"]
  }

  statement {
    sid    = "ProjectBucket"
    effect = "Allow"
    actions = [
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
      "s3:DeleteObject",
    ]
    resources = [
      "arn:aws:s3:::${local.project_bucket}",
      "arn:aws:s3:::${local.project_bucket}/*",
    ]
  }

  statement {
    sid    = "ProjectBucketKmsKey"
    effect = "Allow"
    actions = [
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
      "kms:CancelKeyDeletion",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "cicd_permissions" {
  name   = "terraform-deploy"
  role   = aws_iam_role.cicd_deploy.id
  policy = data.aws_iam_policy_document.cicd_permissions.json
}
