variable "name_prefix" {
  description = "Prefix for resource names."
  type        = string
}

variable "bucket_id" {
  description = "Project S3 bucket name (CloudFront origin)."
  type        = string
}

variable "bucket_arn" {
  description = "Project S3 bucket ARN."
  type        = string
}

variable "bucket_regional_domain_name" {
  description = "Regional domain name of the project bucket."
  type        = string
}

variable "web_prefix" {
  description = "Key prefix holding the SPA build artifacts."
  type        = string
  default     = "web"
}

variable "price_class" {
  description = "CloudFront price class."
  type        = string
  default     = "PriceClass_100"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
