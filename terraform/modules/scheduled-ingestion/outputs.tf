output "cluster_arn" {
  description = "ECS cluster ARN."
  value       = aws_ecs_cluster.this.arn
}

output "task_definition_arn" {
  description = "Ingestion task definition ARN."
  value       = aws_ecs_task_definition.ingest.arn
}

output "schedule_name" {
  description = "EventBridge Scheduler schedule name."
  value       = aws_scheduler_schedule.ingest.name
}

output "alerts_topic_arn" {
  description = "SNS topic for failed-run notifications."
  value       = aws_sns_topic.alerts.arn
}
