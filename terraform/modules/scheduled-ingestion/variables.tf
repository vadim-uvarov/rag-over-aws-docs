variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region."
  type        = string
}

variable "bucket_name" {
  description = "Project S3 bucket name (ingestion target)."
  type        = string
}

variable "bucket_arn" {
  description = "Project S3 bucket ARN."
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key encrypting the project bucket."
  type        = string
}

variable "image_uri" {
  description = "ECR image URI for the ingestion container."
  type        = string
}

variable "schedule_expression" {
  description = "EventBridge Scheduler expression for the ingestion run."
  type        = string
  default     = "rate(24 hours)"
}

variable "subnet_ids" {
  description = "Subnets for the Fargate task (need outbound internet for git/S3)."
  type        = list(string)
  default     = []
}

variable "security_group_ids" {
  description = "Security groups for the Fargate task."
  type        = list(string)
  default     = []
}

variable "assign_public_ip" {
  description = "Assign a public IP (true for public subnets without a NAT gateway)."
  type        = bool
  default     = true
}

variable "task_cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory (MiB)."
  type        = number
  default     = 1024
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the ingestion task."
  type        = number
  default     = 14
}

variable "alarm_email" {
  description = "Optional email subscribed to the failed-run SNS topic."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
