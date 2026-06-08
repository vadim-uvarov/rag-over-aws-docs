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

output "etl_ingest_queue_url" {
  description = "ETL ingestion SQS queue URL (null when ETL is disabled)."
  value       = try(module.etl[0].ingest_queue_url, null)
}

output "etl_state_machine_arn" {
  description = "ETL Step Functions state machine ARN (null when ETL is disabled)."
  value       = try(module.etl[0].state_machine_arn, null)
}
