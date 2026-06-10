output "distribution_id" {
  description = "CloudFront distribution id (for cache invalidation on deploy)."
  value       = aws_cloudfront_distribution.web.id
}

output "distribution_domain_name" {
  description = "CloudFront domain name serving the SPA."
  value       = aws_cloudfront_distribution.web.domain_name
}
