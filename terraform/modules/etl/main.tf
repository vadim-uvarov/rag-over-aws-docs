terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

# --- SQS buffer + dead-letter queue ----------------------------------------

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name_prefix}-etl-dlq"
  message_retention_seconds = 1209600 # 14 days
  tags                      = var.tags
}

resource "aws_sqs_queue" "ingest" {
  name                       = "${var.name_prefix}-etl-ingest"
  visibility_timeout_seconds = var.process_timeout_seconds * 6 # >= Lambda timeout
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
  tags = var.tags
}

# --- EventBridge: S3 object events on corpus/raw/ → SQS ---------------------

resource "aws_s3_bucket_notification" "eventbridge" {
  bucket      = var.bucket_name
  eventbridge = true
}

resource "aws_cloudwatch_event_rule" "raw_objects" {
  name        = "${var.name_prefix}-etl-raw-objects"
  description = "S3 create/delete events under corpus/raw/"
  event_pattern = jsonencode({
    source        = ["aws.s3"]
    "detail-type" = ["Object Created", "Object Deleted"]
    detail = {
      bucket = { name = [var.bucket_name] }
      object = { key = [{ prefix = "corpus/raw/" }] }
    }
  })
  tags = var.tags
}

resource "aws_cloudwatch_event_target" "to_sqs" {
  rule = aws_cloudwatch_event_rule.raw_objects.name
  arn  = aws_sqs_queue.ingest.arn
}

data "aws_iam_policy_document" "queue_policy" {
  statement {
    sid       = "AllowEventBridge"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.ingest.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudwatch_event_rule.raw_objects.arn]
    }
  }
}

resource "aws_sqs_queue_policy" "ingest" {
  queue_url = aws_sqs_queue.ingest.id
  policy    = data.aws_iam_policy_document.queue_policy.json
}

# --- Lambdas (one container image, two entry commands) ---------------------

resource "aws_cloudwatch_log_group" "process" {
  name              = "/aws/lambda/${var.name_prefix}-etl-process"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "process" {
  function_name = "${var.name_prefix}-etl-process"
  role          = aws_iam_role.process.arn
  package_type  = "Image"
  image_uri     = var.lambda_image_uri
  memory_size   = var.process_memory_mb
  timeout       = var.process_timeout_seconds

  image_config {
    command = ["rag_aws.etl.handlers.process.handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      PROJECT_BUCKET_NAME = var.bucket_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.process]
  tags       = var.tags
}

resource "aws_cloudwatch_log_group" "dispatch" {
  name              = "/aws/lambda/${var.name_prefix}-etl-dispatch"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "dispatch" {
  function_name = "${var.name_prefix}-etl-dispatch"
  role          = aws_iam_role.dispatch.arn
  package_type  = "Image"
  image_uri     = var.lambda_image_uri
  memory_size   = 256
  timeout       = 60

  image_config {
    command = ["rag_aws.etl.handlers.dispatch.handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      STATE_MACHINE_ARN = aws_sfn_state_machine.etl.arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.dispatch]
  tags       = var.tags
}

resource "aws_lambda_event_source_mapping" "sqs_to_dispatch" {
  event_source_arn                   = aws_sqs_queue.ingest.arn
  function_name                      = aws_lambda_function.dispatch.arn
  batch_size                         = var.sqs_batch_size
  maximum_batching_window_in_seconds = var.sqs_batch_window_seconds
}

# --- Step Functions: Map(batch) → process ----------------------------------

resource "aws_sfn_state_machine" "etl" {
  name     = "${var.name_prefix}-etl"
  role_arn = aws_iam_role.sfn.arn

  definition = jsonencode({
    Comment = "ETL: chunk -> embed -> index over a batch of S3 events"
    StartAt = "ProcessBatch"
    States = {
      ProcessBatch = {
        Type                       = "Map"
        ItemsPath                  = "$.items"
        MaxConcurrency             = var.map_max_concurrency
        ToleratedFailurePercentage = 20
        ItemProcessor = {
          ProcessorConfig = { Mode = "INLINE" }
          StartAt         = "ProcessDocument"
          States = {
            ProcessDocument = {
              Type     = "Task"
              Resource = "arn:aws:states:::lambda:invoke"
              Parameters = {
                FunctionName = aws_lambda_function.process.arn
                "Payload.$"  = "$"
              }
              Retry = [{
                ErrorEquals = [
                  "Lambda.TooManyRequestsException",
                  "Lambda.ServiceException",
                  "States.TaskFailed",
                ]
                IntervalSeconds = 2
                MaxAttempts     = 4
                BackoffRate     = 2.0
              }]
              End = true
            }
          }
        }
        End = true
      }
    }
  })

  tags = var.tags
}
