variable "bucket_name" {
  description = "Globally-unique name for the project S3 bucket."
  type        = string
}

variable "tags" {
  description = "Tags applied to every resource in this module."
  type        = map(string)
  default     = {}
}

variable "noncurrent_version_expiration_days" {
  description = "Days to retain noncurrent object versions before expiry."
  type        = number
  default     = 30
}
