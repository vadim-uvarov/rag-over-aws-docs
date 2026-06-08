output "ingest_queue_url" {
  description = "URL of the ETL ingestion SQS queue (backfill target)."
  value       = aws_sqs_queue.ingest.id
}

output "ingest_queue_arn" {
  description = "ARN of the ETL ingestion SQS queue."
  value       = aws_sqs_queue.ingest.arn
}

output "dlq_arn" {
  description = "ARN of the ETL dead-letter queue."
  value       = aws_sqs_queue.dlq.arn
}

output "state_machine_arn" {
  description = "ARN of the ETL Step Functions state machine."
  value       = aws_sfn_state_machine.etl.arn
}

output "process_function_name" {
  description = "Name of the process Lambda."
  value       = aws_lambda_function.process.function_name
}
