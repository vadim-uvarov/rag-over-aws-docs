data "aws_caller_identity" "current" {}

locals {
  bedrock_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.embed_model_id}"
}

# --- Trust policy shared by the Lambda roles -------------------------------

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# --- Process Lambda role: read raw, write chunks, embed, use KMS -----------

resource "aws_iam_role" "process" {
  name               = "${var.name_prefix}-etl-process"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "process" {
  statement {
    sid       = "ObjectAccess"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${var.bucket_arn}/*"]
  }
  statement {
    sid       = "ListBucket"
    actions   = ["s3:ListBucket"]
    resources = [var.bucket_arn]
  }
  statement {
    sid       = "Kms"
    actions   = ["kms:Decrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn]
  }
  statement {
    sid       = "Bedrock"
    actions   = ["bedrock:InvokeModel"]
    resources = [local.bedrock_model_arn]
  }
}

resource "aws_iam_role_policy" "process" {
  name   = "access"
  role   = aws_iam_role.process.id
  policy = data.aws_iam_policy_document.process.json
}

resource "aws_iam_role_policy_attachment" "process_logs" {
  role       = aws_iam_role.process.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Dispatch Lambda role: read SQS, start executions ----------------------

resource "aws_iam_role" "dispatch" {
  name               = "${var.name_prefix}-etl-dispatch"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "dispatch" {
  statement {
    sid       = "Sqs"
    actions   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
    resources = [aws_sqs_queue.ingest.arn]
  }
  statement {
    sid       = "StartExecution"
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.etl.arn]
  }
}

resource "aws_iam_role_policy" "dispatch" {
  name   = "access"
  role   = aws_iam_role.dispatch.id
  policy = data.aws_iam_policy_document.dispatch.json
}

resource "aws_iam_role_policy_attachment" "dispatch_logs" {
  role       = aws_iam_role.dispatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# --- Step Functions role: invoke the process Lambda ------------------------

data "aws_iam_policy_document" "sfn_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sfn" {
  name               = "${var.name_prefix}-etl-sfn"
  assume_role_policy = data.aws_iam_policy_document.sfn_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "sfn" {
  statement {
    sid       = "InvokeProcess"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.process.arn]
  }
}

resource "aws_iam_role_policy" "sfn" {
  name   = "access"
  role   = aws_iam_role.sfn.id
  policy = data.aws_iam_policy_document.sfn.json
}
