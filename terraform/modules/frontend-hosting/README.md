# frontend-hosting module

Serves the React SPA from the project bucket's `web/` prefix through CloudFront.

- **Origin Access Control (OAC)** — only this CloudFront distribution can read
  the bucket; public access stays blocked. The bucket uses SSE-S3, so CloudFront
  serves objects without any KMS decrypt grant.
- **CloudFront distribution** — origin path `/web`, `index.html` default root,
  HTTPS redirect, default CloudFront certificate.
- **SPA routing** — `403`/`404` are rewritten to `/index.html` (200).
- **Bucket policy** — grants `s3:GetObject` on `web/*` only to this
  distribution (`AWS:SourceArn` condition).

## Deploying the SPA

Build and upload, then invalidate the cache:

```sh
scripts/deploy_frontend.sh <bucket> <distribution-id> [api-url]
```

## Inputs / outputs

Inputs: `name_prefix`, `bucket_id`, `bucket_arn`, `bucket_regional_domain_name`.
Outputs: `distribution_id` (for invalidation), `distribution_domain_name`.

Gated behind `enable_frontend` in `terraform/prod`.
