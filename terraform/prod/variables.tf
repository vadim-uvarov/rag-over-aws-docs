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

variable "enable_frontend" {
  description = "Provision the CloudFront frontend hosting module."
  type        = bool
  default     = false
}

variable "enable_monitoring" {
  description = "Provision dashboards + alarms (requires enable_etl and enable_query_api)."
  type        = bool
  default     = false
}

variable "alarm_email" {
  description = "Optional email subscribed to the alerts SNS topic."
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

variable "enable_scheduled_ingestion" {
  description = "Provision scheduled Fargate corpus ingestion (requires an ECR image)."
  type        = bool
  default     = false
}

variable "ingestion_image_uri" {
  description = "ECR image URI for the ingestion container."
  type        = string
  default     = ""
}

variable "ingestion_subnet_ids" {
  description = "Subnets for the ingestion Fargate task."
  type        = list(string)
  default     = []
}

variable "ingestion_security_group_ids" {
  description = "Security groups for the ingestion Fargate task."
  type        = list(string)
  default     = []
}
