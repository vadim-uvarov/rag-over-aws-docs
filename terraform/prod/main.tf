# Placeholder prod stack. It provisions nothing yet — `terraform apply` just prints a
# message. Replace the null_resource with real infrastructure as the project grows.

terraform {
  required_version = ">= 1.5"

  # Remote state in S3 with S3-native locking. The bucket name embeds the AWS
  # account ID, so it is supplied at init time rather than hardcoded here:
  #   terraform -chdir=terraform/prod init \
  #     -backend-config="bucket=<project>-tfstate-<account_id>"
  # Run scripts/create-bucket-for-tfstate-in-aws.sh once per account to create the bucket.
  backend "s3" {
    key          = "prod/terraform.tfstate"
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true
  }

  required_providers {
    null = {
      source  = "hashicorp/null"
      version = ">= 3.2"
    }
  }
}

resource "null_resource" "deploy_message" {
  provisioner "local-exec" {
    command = "echo 'Deploying rag-over-aws-docs to PROD (placeholder — nothing provisioned yet).'"
  }

  # Re-run the message on every apply.
  triggers = {
    always_run = timestamp()
  }
}
