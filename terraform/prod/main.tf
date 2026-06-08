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

  bucket_name = "${local.project}-${local.environment}-${data.aws_caller_identity.current.account_id}"
}

module "storage" {
  source = "../modules/storage"

  bucket_name = local.bucket_name
  tags        = local.common_tags
}
