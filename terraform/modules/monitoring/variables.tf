variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "aws_region" {
  description = "AWS region (for dashboard widgets)."
  type        = string
}

variable "alarm_email" {
  description = "Optional email subscribed to the alerts SNS topic."
  type        = string
  default     = ""
}

variable "state_machine_arn" {
  description = "ETL Step Functions state machine ARN."
  type        = string
}

variable "dlq_name" {
  description = "ETL dead-letter queue name."
  type        = string
}

variable "api_name" {
  description = "REST API name."
  type        = string
}

variable "lambda_function_names" {
  description = "Lambda function names to alarm on errors and chart."
  type        = list(string)
}

variable "query_function_name" {
  description = "Query Lambda name (latency/error focus)."
  type        = string
}

variable "api_5xx_threshold" {
  description = "5XX count over the period that trips the API alarm."
  type        = number
  default     = 5
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
