output "deploy_role_arn" {
  description = "ARN of the CI/CD deploy role. Set as AWS_ROLE_ARN on the prod GitHub Environment."
  value       = aws_iam_role.cicd_deploy.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider."
  value       = aws_iam_openid_connect_provider.github.arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository CI tags and pushes the Lambda image to."
  value       = aws_ecr_repository.lambda.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository holding the Lambda image."
  value       = aws_ecr_repository.lambda.arn
}
