variable "name_prefix" {
  description = "Prefix for resource names (e.g. rag-over-aws-docs-prod)."
  type        = string
}

variable "aws_region" {
  description = "AWS region (used to scope the Bedrock model ARN)."
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

variable "kms_key_arn" {
  description = "ARN of the KMS key encrypting the project bucket."
  type        = string
}

variable "lambda_image_uri" {
  description = "ECR image URI for the ETL Lambdas (dispatch + process share one image)."
  type        = string
}

variable "embed_model_id" {
  description = "Bedrock embedding model id, for the InvokeModel IAM resource."
  type        = string
  default     = "amazon.titan-embed-text-v2:0"
}

variable "process_memory_mb" {
  description = "Memory for the process Lambda (LanceDB/pyarrow are heavy)."
  type        = number
  default     = 2048
}

variable "process_timeout_seconds" {
  description = "Timeout for the process Lambda."
  type        = number
  default     = 300
}

variable "sqs_batch_size" {
  description = "Max SQS messages the dispatcher receives per invocation."
  type        = number
  default     = 10
}

variable "sqs_batch_window_seconds" {
  description = "Max seconds to buffer SQS messages before invoking the dispatcher."
  type        = number
  default     = 30
}

variable "map_max_concurrency" {
  description = "Max concurrent document processors in the Map state (Bedrock throttling control)."
  type        = number
  default     = 5
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the ETL Lambdas."
  type        = number
  default     = 14
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
