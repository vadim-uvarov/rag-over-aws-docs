terraform {
  required_version = ">= 1.5"

  # Remote state in S3 with S3-native locking. The bucket name embeds the AWS
  # account ID, so it is supplied at init time rather than hardcoded here.
  backend "s3" {
    key          = "prod/terraform.tfstate"
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

# The deploying account; used to make the project bucket name globally unique.
data "aws_caller_identity" "current" {}

locals {
  project     = "rag-over-aws-docs"
  environment = "prod"

  common_tags = {
    Project     = local.project
    Environment = local.environment
    ManagedBy   = "terraform"
  }

  name_prefix = "${local.project}-${local.environment}"
  bucket_name = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}"
}

module "storage" {
  source = "../modules/storage"

  bucket_name = local.bucket_name
  tags        = local.common_tags
}

# ETL orchestration. Disabled until the Lambda container image exists in ECR
# (set enable_etl=true and etl_lambda_image_uri after building backend/Dockerfile).
module "etl" {
  source = "../modules/etl"
  count  = var.enable_etl ? 1 : 0

  name_prefix      = local.name_prefix
  aws_region       = var.aws_region
  bucket_name      = module.storage.bucket_id
  bucket_arn       = module.storage.bucket_arn
  kms_key_arn      = module.storage.kms_key_arn
  lambda_image_uri = var.etl_lambda_image_uri
  tags             = local.common_tags
}

# Frontend hosting (CloudFront + OAC over web/). Disabled by default; enable to
# provision the distribution, then deploy the SPA with scripts/deploy_frontend.sh.
module "frontend" {
  source = "../modules/frontend-hosting"
  count  = var.enable_frontend ? 1 : 0

  name_prefix                 = local.name_prefix
  bucket_id                   = module.storage.bucket_id
  bucket_arn                  = module.storage.bucket_arn
  bucket_regional_domain_name = module.storage.bucket_regional_domain_name
  tags                        = local.common_tags
}

# RAG query API. Disabled until the Lambda container image exists in ECR.
module "query_api" {
  source = "../modules/query-api"
  count  = var.enable_query_api ? 1 : 0

  name_prefix      = local.name_prefix
  aws_region       = var.aws_region
  bucket_name      = module.storage.bucket_id
  bucket_arn       = module.storage.bucket_arn
  kms_key_arn      = module.storage.kms_key_arn
  lambda_image_uri = var.query_lambda_image_uri
  tags             = local.common_tags
}

# Dashboards + alarms. Requires enable_etl and enable_query_api (it monitors
# their resources). Disabled by default.
module "monitoring" {
  source = "../modules/monitoring"
  count  = var.enable_monitoring ? 1 : 0

  name_prefix         = local.name_prefix
  aws_region          = var.aws_region
  alarm_email         = var.alarm_email
  state_machine_arn   = module.etl[0].state_machine_arn
  dlq_name            = module.etl[0].dlq_name
  api_name            = module.query_api[0].api_name
  query_function_name = module.query_api[0].query_function_name
  lambda_function_names = [
    module.etl[0].process_function_name,
    module.etl[0].dispatch_function_name,
    module.query_api[0].query_function_name,
  ]
  tags = local.common_tags
}
