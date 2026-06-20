variable "name_prefix" {
  description = "Prefix for resource names (e.g. rag-over-aws-docs-prod)."
  type        = string
}

variable "aws_region" {
  description = "AWS region (used to scope Bedrock model ARNs)."
  type        = string
}

variable "bucket_name" {
  description = "Project S3 bucket name."
  type        = string
}

variable "bucket_arn" {
  description = "Project S3 bucket ARN."
  type        = string
}

variable "lambda_image_uri" {
  description = "ECR image URI for the query Lambda."
  type        = string
}

variable "embed_model_id" {
  description = "Bedrock embedding model id."
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "generation_model_id" {
  description = "Bedrock generation model id."
  type        = string
  default     = "amazon.nova-micro-v1:0"
}

variable "session_question_limit" {
  description = "Max questions per session."
  type        = number
  default     = 20
}

variable "session_ttl_hours" {
  description = "Session counter TTL in hours."
  type        = number
  default     = 24
}

variable "stage_name" {
  description = "API Gateway stage name."
  type        = string
  default     = "prod"
}

variable "daily_request_quota" {
  description = "Global daily request cap (API Gateway usage plan)."
  type        = number
  default     = 5000
}

variable "throttle_rate_limit" {
  description = "Steady-state requests/second (usage plan + stage throttle)."
  type        = number
  default     = 20
}

variable "throttle_burst_limit" {
  description = "Burst request capacity."
  type        = number
  default     = 40
}

variable "waf_ip_rate_limit" {
  description = "Max requests per IP per 5-minute window (WAF rate rule)."
  type        = number
  default     = 300
}

variable "bedrock_monthly_budget_usd" {
  description = "Monthly Bedrock cost budget that triggers an SNS alarm."
  type        = number
  default     = 50
}

variable "budget_alarm_email" {
  description = "Optional email subscribed to the Bedrock budget SNS topic."
  type        = string
  default     = ""
}

variable "langfuse_secret_name" {
  description = "Secrets Manager secret holding Langfuse keys."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the query Lambda."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
