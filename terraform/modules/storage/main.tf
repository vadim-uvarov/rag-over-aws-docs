terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# Single project bucket. Prefix layout (see README.md):
#   corpus/raw/ (A)  corpus/chunks/ (B)  corpus/vector-store/ (C)
#   corpus/manifests/ (D)  web/ (frontend artifacts)
resource "aws_s3_bucket" "project" {
  bucket = var.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "project" {
  bucket = aws_s3_bucket.project.id
  versioning_configuration {
    status = "Enabled"
  }
}

# SSE-S3 (AES256): S3-managed keys, no KMS. The corpus is public AWS docs and
# all public access is blocked, so a customer-managed key is unnecessary cost.
resource "aws_s3_bucket_server_side_encryption_configuration" "project" {
  bucket = aws_s3_bucket.project.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# CloudFront reaches web/ via OAC only (added in PR6); nothing is ever public.
resource "aws_s3_bucket_public_access_block" "project" {
  bucket                  = aws_s3_bucket.project.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioning is on, so prune old noncurrent versions to control storage cost.
resource "aws_s3_bucket_lifecycle_configuration" "project" {
  bucket = aws_s3_bucket.project.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"

    filter {} # apply to all objects

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }
  }
}
