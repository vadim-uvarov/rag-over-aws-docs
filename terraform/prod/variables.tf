variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-west-1"
}

variable "enable_etl" {
  description = "Provision the ETL orchestration module (requires a built Lambda image)."
  type        = bool
  default     = false
}

variable "etl_lambda_image_uri" {
  description = "ECR image URI for the ETL Lambdas (required when enable_etl=true)."
  type        = string
  default     = ""
}

variable "enable_query_api" {
  description = "Provision the RAG query API module (requires a built Lambda image)."
  type        = bool
  default     = false
}

variable "query_lambda_image_uri" {
  description = "ECR image URI for the query Lambda (required when enable_query_api=true)."
  type        = string
  default     = ""
}
