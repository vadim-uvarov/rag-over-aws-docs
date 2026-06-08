terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

locals {
  langfuse_secret_name = var.langfuse_secret_name != "" ? var.langfuse_secret_name : "${var.name_prefix}-langfuse"
}

# --- Per-session quota table (24h TTL) -------------------------------------

resource "aws_dynamodb_table" "sessions" {
  name         = "${var.name_prefix}-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  tags = var.tags
}

# --- Langfuse keys secret (value populated out of band) --------------------

resource "aws_secretsmanager_secret" "langfuse" {
  name                    = local.langfuse_secret_name
  description             = "Langfuse Cloud keys for RAG tracing (public_key/secret_key/host)"
  recovery_window_in_days = 0
  tags                    = var.tags
}

# --- Query Lambda ----------------------------------------------------------

resource "aws_cloudwatch_log_group" "query" {
  name              = "/aws/lambda/${var.name_prefix}-query"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "query" {
  function_name = "${var.name_prefix}-query"
  role          = aws_iam_role.query.arn
  package_type  = "Image"
  image_uri     = var.lambda_image_uri
  memory_size   = 2048
  timeout       = 30

  image_config {
    command = ["rag_aws.query.handler.handler"]
  }

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      PROJECT_BUCKET_NAME  = var.bucket_name
      SESSION_TABLE_NAME   = aws_dynamodb_table.sessions.name
      LANGFUSE_SECRET_NAME = local.langfuse_secret_name
    }
  }

  depends_on = [aws_cloudwatch_log_group.query]
  tags       = var.tags
}

# --- REST API: POST /ask (Lambda proxy) ------------------------------------

resource "aws_api_gateway_rest_api" "api" {
  name        = "${var.name_prefix}-api"
  description = "Synchronous RAG /ask endpoint"
  tags        = var.tags
}

resource "aws_api_gateway_resource" "ask" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "ask"
}

resource "aws_api_gateway_method" "post_ask" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.ask.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.ask.id
  http_method             = aws_api_gateway_method.post_ask.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.query.invoke_arn
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "this" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  triggers = {
    redeploy = sha1(jsonencode([
      aws_api_gateway_resource.ask.id,
      aws_api_gateway_method.post_ask.id,
      aws_api_gateway_integration.lambda.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "this" {
  rest_api_id          = aws_api_gateway_rest_api.api.id
  deployment_id        = aws_api_gateway_deployment.this.id
  stage_name           = var.stage_name
  xray_tracing_enabled = true
  tags                 = var.tags
}

resource "aws_api_gateway_method_settings" "throttle" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  stage_name  = aws_api_gateway_stage.this.stage_name
  method_path = "*/*"

  settings {
    throttling_rate_limit  = var.throttle_rate_limit
    throttling_burst_limit = var.throttle_burst_limit
    metrics_enabled        = true
  }
}

# --- Usage plan: global daily quota + throttle -----------------------------

resource "aws_api_gateway_usage_plan" "this" {
  name = "${var.name_prefix}-usage-plan"

  api_stages {
    api_id = aws_api_gateway_rest_api.api.id
    stage  = aws_api_gateway_stage.this.stage_name
  }

  quota_settings {
    limit  = var.daily_request_quota
    period = "DAY"
  }

  throttle_settings {
    rate_limit  = var.throttle_rate_limit
    burst_limit = var.throttle_burst_limit
  }

  tags = var.tags
}
