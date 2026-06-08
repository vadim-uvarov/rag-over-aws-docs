# Per-IP rate limiting in front of the API stage.

resource "aws_wafv2_web_acl" "api" {
  name        = "${var.name_prefix}-api-waf"
  description = "Per-IP rate limiting for the RAG API"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "per-ip-rate-limit"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_ip_rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-per-ip-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.name_prefix}-api-waf"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_api_gateway_stage.this.arn
  web_acl_arn  = aws_wafv2_web_acl.api.arn
}
