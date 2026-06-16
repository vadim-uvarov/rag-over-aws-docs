variable "github_repo" {
  description = "GitHub repository (owner/name) whose prod environment may assume the deploy role."
  type        = string
}

variable "environment" {
  description = "Deployment environment; scopes the role trust policy and the bucket names it grants access to."
  type        = string
  default     = "prod"
}
