terraform {
  required_version = ">= 1.5"

  # Bootstrap state lives in the same bucket as the prod stack, under a separate
  # key. The bucket is created out-of-band (scripts/setup-repo-and-infra/create-tfstate-bucket-in-aws.sh)
  # because it must exist before any Terraform runs. The bucket name embeds the
  # account ID and the region mirrors local.aws_region (sourced from
  # config/deploy.json, the single source of truth for the region), so both are
  # supplied at init time via -backend-config rather than hardcoded here.
  backend "s3" {
    key          = "bootstrap/terraform.tfstate"
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
  region = local.aws_region

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

  # Single source of truth for the AWS region, shared with the prod stack and the
  # CI/CD workflow (see config/deploy.json).
  aws_region = jsondecode(file("${path.module}/../../config/deploy.json")).aws_region

  common_tags = {
    Project     = local.project
    Environment = local.environment
    ManagedBy   = "terraform"
  }

  # Bucket names must stay in sync with scripts/setup-repo-and-infra/create-tfstate-bucket-in-aws.sh
  # and terraform/prod (project-environment-accountid).
  tfstate_bucket = "${local.project}-tfstate-${data.aws_caller_identity.current.account_id}"
  project_bucket = "${local.project}-${local.environment}-${data.aws_caller_identity.current.account_id}"

  # The prod stack names every resource it creates with this prefix, so the
  # deploy role's per-service permissions are scoped to "<prefix>-*" ARNs.
  prod_prefix = "${local.project}-${local.environment}"
  account_id  = data.aws_caller_identity.current.account_id
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

# Permissions, in broad groups:
#   1. Terraform state bucket (init/plan/apply + S3-native locking).
#   2. The project S3 bucket the prod stack creates and manages. Terraform reads
#      back every bucket sub-resource (versioning, encryption, lifecycle, public
#      access block, tagging, ...) on each apply, so the role needs the matching
#      Get*/Put* actions, not just CreateBucket.
#   3. CloudFront distribution + origin access control for the frontend.
#   4. ECR: token auth (must be "*") plus layer/image push and read/tag actions
#      scoped to this stack's repository, so CI can build and push the image.
#   5. The ETL, Query API and Monitoring modules in terraform/prod. Each apply
#      runs a terraform refresh that reads back every attribute, so these grant
#      full create/read/update/delete/tag on the resource types those modules
#      manage (Lambda, IAM roles, SQS, Step Functions, EventBridge, CloudWatch
#      logs/alarms/dashboards, API Gateway, DynamoDB, SNS, Secrets Manager,
#      Budgets), scoped to "rag-over-aws-docs-prod-*" ARNs where the
#      service supports resource-level permissions and to "*" where it does not.
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

  # CloudFront does not support resource-level restrictions for most actions,
  # so "*" is required.
  statement {
    sid    = "CloudFront"
    effect = "Allow"
    actions = [
      "cloudfront:CreateDistribution",
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:UpdateDistribution",
      "cloudfront:DeleteDistribution",
      "cloudfront:TagResource",
      "cloudfront:ListTagsForResource",
      "cloudfront:UntagResource",
      "cloudfront:CreateOriginAccessControl",
      "cloudfront:GetOriginAccessControl",
      "cloudfront:UpdateOriginAccessControl",
      "cloudfront:DeleteOriginAccessControl",
      "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation",
    ]
    resources = ["*"]
  }

  # ecr:GetAuthorizationToken returns a short-lived registry login token and is
  # not tied to a repository, so AWS only accepts "*" as its resource.
  statement {
    sid       = "EcrAuthToken"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # Push and read the single Lambda image, plus the read/tag actions terraform
  # needs to refresh the repository, all scoped to this stack's repository.
  statement {
    sid    = "EcrRepository"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:InitiateLayerUpload",
      "ecr:UploadLayerPart",
      "ecr:CompleteLayerUpload",
      "ecr:PutImage",
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
      "ecr:DescribeRepositories",
      "ecr:DescribeImages",
      "ecr:ListImages",
      "ecr:GetRepositoryPolicy",
      "ecr:GetLifecyclePolicy",
      "ecr:ListTagsForResource",
      "ecr:TagResource",
    ]
    resources = [aws_ecr_repository.lambda.arn]
  }

  # All Lambda functions the prod modules create share the "<prefix>-*" name.
  # Event-source mappings (SQS -> Lambda) get server-generated UUIDs, so they
  # cannot be name-scoped and are matched with a wildcard.
  statement {
    sid     = "Lambda"
    effect  = "Allow"
    actions = ["lambda:*"]
    resources = [
      "arn:aws:lambda:${local.aws_region}:${local.account_id}:function:${local.prod_prefix}-*",
      "arn:aws:lambda:${local.aws_region}:${local.account_id}:event-source-mapping:*",
    ]
  }

  # The four module roles (etl-process, etl-dispatch, etl-sfn, query) with their
  # inline policies and managed-policy attachments. PassRole lets Lambda and
  # Step Functions assume them.
  statement {
    sid    = "Iam"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:PutRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:GetRolePolicy",
      "iam:AttachRolePolicy",
      "iam:DetachRolePolicy",
      "iam:PassRole",
      "iam:UpdateAssumeRolePolicy",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/${local.prod_prefix}-*"]
  }

  statement {
    sid       = "Sqs"
    effect    = "Allow"
    actions   = ["sqs:*"]
    resources = ["arn:aws:sqs:${local.aws_region}:${local.account_id}:${local.prod_prefix}-*"]
  }

  # states:* covers tagging actions too (TagResource/UntagResource/ListTagsForResource).
  statement {
    sid       = "StepFunctions"
    effect    = "Allow"
    actions   = ["states:*"]
    resources = ["arn:aws:states:${local.aws_region}:${local.account_id}:stateMachine:${local.prod_prefix}-*"]
  }

  # ValidateStateMachineDefinition checks a definition before any state machine
  # exists, so it has no specific resource to scope to and AWS requires "*". It
  # is therefore split out of the resource-scoped StepFunctions statement above.
  statement {
    sid       = "StepFunctionsValidateDefinition"
    effect    = "Allow"
    actions   = ["states:ValidateStateMachineDefinition"]
    resources = ["*"]
  }

  statement {
    sid       = "EventBridge"
    effect    = "Allow"
    actions   = ["events:*"]
    resources = ["arn:aws:events:${local.aws_region}:${local.account_id}:rule/${local.prod_prefix}-*"]
  }

  # Lambda log groups and their streams (the ":*" suffix matches stream ARNs).
  statement {
    sid     = "CloudWatchLogs"
    effect  = "Allow"
    actions = ["logs:*"]
    resources = [
      "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/lambda/${local.prod_prefix}-*",
      "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/lambda/${local.prod_prefix}-*:*",
    ]
  }

  # logs:DescribeLogGroups does not support resource-level scoping, so it is
  # granted separately on "*".
  statement {
    sid       = "CloudWatchLogsDescribe"
    effect    = "Allow"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  # CloudWatch alarms and dashboards do not support resource-level scoping on
  # create, so these actions require "*" (same pattern as CloudFront above).
  statement {
    sid    = "CloudWatch"
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricAlarm",
      "cloudwatch:DeleteAlarms",
      "cloudwatch:DescribeAlarms",
      "cloudwatch:ListTagsForResource",
      "cloudwatch:TagResource",
      "cloudwatch:UntagResource",
      "cloudwatch:PutDashboard",
      "cloudwatch:GetDashboard",
      "cloudwatch:ListDashboards",
      "cloudwatch:DeleteDashboards",
    ]
    resources = ["*"]
  }

  # API Gateway ARNs carry no account-id segment (arn:aws:apigateway:<region>::/...).
  statement {
    sid       = "ApiGateway"
    effect    = "Allow"
    actions   = ["apigateway:*"]
    resources = ["arn:aws:apigateway:${local.aws_region}::/*"]
  }

  statement {
    sid       = "DynamoDb"
    effect    = "Allow"
    actions   = ["dynamodb:*"]
    resources = ["arn:aws:dynamodb:${local.aws_region}:${local.account_id}:table/${local.prod_prefix}-*"]
  }

  statement {
    sid       = "Sns"
    effect    = "Allow"
    actions   = ["sns:*"]
    resources = ["arn:aws:sns:${local.aws_region}:${local.account_id}:${local.prod_prefix}-*"]
  }

  # Secret ARNs end in a random 6-char suffix; the "<prefix>-*" wildcard covers it.
  statement {
    sid       = "SecretsManager"
    effect    = "Allow"
    actions   = ["secretsmanager:*"]
    resources = ["arn:aws:secretsmanager:${local.aws_region}:${local.account_id}:secret:${local.prod_prefix}-*"]
  }

  # Budgets are a global service with no region segment in their ARNs.
  statement {
    sid       = "Budgets"
    effect    = "Allow"
    actions   = ["budgets:*"]
    resources = ["arn:aws:budgets::${local.account_id}:budget/*"]
  }
}

resource "aws_iam_role_policy" "cicd_permissions" {
  name   = "terraform-deploy"
  role   = aws_iam_role.cicd_deploy.id
  policy = data.aws_iam_policy_document.cicd_permissions.json
}
