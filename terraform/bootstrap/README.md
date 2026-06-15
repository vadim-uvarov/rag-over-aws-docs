# Bootstrap stack

One-time setup of the AWS identity the CI/CD pipeline assumes. It manages:

- the **GitHub Actions OIDC identity provider** (`token.actions.githubusercontent.com`);
- the **deploy IAM role** (`rag-over-aws-docs-cicd-deploy`), trusting that provider
  and scoped to this repo's `prod` environment;
- the role's **permissions policy** — access to the Terraform state bucket plus the
  project bucket and KMS key that the [`prod`](../prod) stack provisions.

Keeping these in Terraform (rather than a shell script) means a permission change
rides in the same diff as the resource that needs it: when a `prod` module starts
managing a new resource type, add the matching actions here and re-apply.

## Why a separate stack and state

This stack is applied **once, by an administrator with broad IAM rights**, and is
deliberately kept out of the `prod` stack — the deploy role cannot be allowed to
rewrite its own trust policy or permissions. Its state is stored under the
`bootstrap/terraform.tfstate` key, separate from `prod/terraform.tfstate`.

## Apply

Prerequisite: the state bucket exists (`scripts/create-tfstate-bucket-in-aws.sh`).

```sh
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

# The region comes from config/deploy.json (the single source of truth) and is
# supplied at init time, since backend blocks cannot interpolate variables.
AWS_REGION="$(jq -er .aws_region config/deploy.json)"

terraform -chdir=terraform/bootstrap init -input=false \
  -backend-config="bucket=rag-over-aws-docs-tfstate-${ACCOUNT_ID}" \
  -backend-config="region=${AWS_REGION}"

terraform -chdir=terraform/bootstrap apply \
  -var="github_repo=<owner>/<name>"
```

Then read the role ARN for the `prod` GitHub Environment:

```sh
terraform -chdir=terraform/bootstrap output -raw deploy_role_arn
```

Set it as `AWS_ROLE_ARN` (see `scripts/setup-deploy-vars-in-github.sh`).
