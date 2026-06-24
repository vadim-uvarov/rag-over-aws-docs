ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
AWS_REGION="$(jq -er .aws_region config/deploy.json)"
terraform -chdir=terraform/bootstrap init -input=false \
    -backend-config="bucket=rag-over-aws-docs-tfstate-${ACCOUNT_ID}" \
    -backend-config="region=${AWS_REGION}"
terraform -chdir=terraform/bootstrap apply \
    -var="github_repo=vadim-uvarov/rag-over-aws-docs"
