# storage module

Provisions the single project S3 bucket used by the whole stack.

The bucket is **versioned**, encrypted with a customer-managed **KMS** key
(SSE-KMS, bucket keys enabled), has **all public access blocked**, and expires
noncurrent object versions on a lifecycle rule.

## Prefix layout

The project uses one bucket with a documented key convention (S3 has no real
folders — these are key prefixes):

| Prefix | Placeholder | Contents |
|---|---|---|
| `corpus/raw/` | A | Raw AWS markdown, key = `<repo>/<path>.md` |
| `corpus/chunks/` | B | Plain-text chunks, key = `<repo>/<doc>/<chunk-index>.txt` |
| `corpus/vector-store/` | C | LanceDB table(s): embeddings + chunk metadata |
| `corpus/manifests/` | D | Ingestion state: per-file content hashes + chunk inventory |
| `web/` | — | Frontend build artifacts (CloudFront origin, added in PR6) |

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `bucket_name` | string | — | Globally-unique bucket name (required) |
| `tags` | map(string) | `{}` | Tags applied to every resource |
| `noncurrent_version_expiration_days` | number | `30` | Retention for noncurrent versions |

## Outputs

| Name | Description |
|---|---|
| `bucket_id` | Bucket name |
| `bucket_arn` | Bucket ARN |
| `kms_key_arn` | KMS key ARN (grant Bedrock/Lambda/CloudFront access in later PRs) |
