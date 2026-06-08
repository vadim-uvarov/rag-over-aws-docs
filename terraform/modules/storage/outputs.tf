output "bucket_id" {
  description = "Name of the project S3 bucket."
  value       = aws_s3_bucket.project.id
}

output "bucket_arn" {
  description = "ARN of the project S3 bucket."
  value       = aws_s3_bucket.project.arn
}

output "kms_key_arn" {
  description = "ARN of the KMS key encrypting the project bucket."
  value       = aws_kms_key.bucket.arn
}
