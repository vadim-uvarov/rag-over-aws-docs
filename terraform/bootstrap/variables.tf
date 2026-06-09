variable "github_repo" {
  description = "GitHub repository (owner/name) whose prod environment may assume the deploy role."
  type        = string
}

variable "aws_region" {
  description = "AWS region for the provider."
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Deployment environment; scopes the role trust policy and the bucket names it grants access to."
  type        = string
  default     = "prod"
}
