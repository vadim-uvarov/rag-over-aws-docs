data "aws_caller_identity" "current" {}

locals {
  bedrock_model_arns = [
    "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.embed_model_id}",
    "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.generation_model_id}",
    "arn:aws:bedrock:${var.aws_region}:${data.aws_caller_identity.current.account_id}:inference-profile/*",
  ]
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "query" {
  name               = "${var.name_prefix}-query"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "query" {
  statement {
    sid       = "ReadCorpus"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [var.bucket_arn, "${var.bucket_arn}/*"]
  }
  statement {
    sid       = "Kms"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn]
  }
  statement {
    sid       = "Bedrock"
    actions   = ["bedrock:InvokeModel"]
    resources = local.bedrock_model_arns
  }
  statement {
    sid       = "SessionQuota"
    actions   = ["dynamodb:UpdateItem", "dynamodb:GetItem"]
    resources = [aws_dynamodb_table.sessions.arn]
  }
  statement {
    sid       = "LangfuseSecret"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.langfuse.arn]
  }
}

resource "aws_iam_role_policy" "query" {
  name   = "access"
  role   = aws_iam_role.query.id
  policy = data.aws_iam_policy_document.query.json
}

resource "aws_iam_role_policy_attachment" "query_logs" {
  role       = aws_iam_role.query.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "query_xray" {
  role       = aws_iam_role.query.name
  policy_arn = "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"
}
