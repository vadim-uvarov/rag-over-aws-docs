output "bucket_id" {
  description = "Name of the project S3 bucket."
  value       = aws_s3_bucket.project.id
}

output "bucket_arn" {
  description = "ARN of the project S3 bucket."
  value       = aws_s3_bucket.project.arn
}

output "bucket_regional_domain_name" {
  description = "Regional domain name of the bucket (CloudFront origin)."
  value       = aws_s3_bucket.project.bucket_regional_domain_name
}
