output "api_invoke_url" {
  description = "Base invoke URL for the API stage."
  value       = aws_api_gateway_stage.this.invoke_url
}

output "ask_endpoint" {
  description = "Full URL of the POST /ask endpoint."
  value       = "${aws_api_gateway_stage.this.invoke_url}/ask"
}

output "sessions_table_name" {
  description = "DynamoDB session-quota table name."
  value       = aws_dynamodb_table.sessions.name
}

output "langfuse_secret_arn" {
  description = "ARN of the Langfuse keys secret (populate its value out of band)."
  value       = aws_secretsmanager_secret.langfuse.arn
}

output "query_function_name" {
  description = "Name of the query Lambda."
  value       = aws_lambda_function.query.function_name
}

output "api_name" {
  description = "REST API name (CloudWatch ApiName dimension)."
  value       = aws_api_gateway_rest_api.api.name
}

output "budget_topic_arn" {
  description = "SNS topic ARN for the Bedrock budget alarm."
  value       = aws_sns_topic.budget.arn
}
