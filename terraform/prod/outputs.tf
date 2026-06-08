output "bucket_name" {
  description = "Name of the project S3 bucket."
  value       = module.storage.bucket_id
}

output "bucket_arn" {
  description = "ARN of the project S3 bucket."
  value       = module.storage.bucket_arn
}

output "kms_key_arn" {
  description = "ARN of the KMS key encrypting the project bucket."
  value       = module.storage.kms_key_arn
}
