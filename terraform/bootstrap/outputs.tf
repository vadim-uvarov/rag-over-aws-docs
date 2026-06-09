output "deploy_role_arn" {
  description = "ARN of the CI/CD deploy role. Set as AWS_ROLE_ARN on the prod GitHub Environment."
  value       = aws_iam_role.cicd_deploy.arn
}

output "oidc_provider_arn" {
  description = "ARN of the GitHub Actions OIDC identity provider."
  value       = aws_iam_openid_connect_provider.github.arn
}
