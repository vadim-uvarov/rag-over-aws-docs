#!/usr/bin/env bash
# Build the SPA and deploy it to the project bucket's web/ prefix, then
# invalidate the CloudFront cache.
#
# Usage: scripts/deploy_frontend.sh <bucket> <distribution-id> [api-url]
set -euo pipefail

BUCKET="${1:?usage: deploy_frontend.sh <bucket> <distribution-id> [api-url]}"
DISTRIBUTION_ID="${2:?usage: deploy_frontend.sh <bucket> <distribution-id> [api-url]}"
API_URL="${3:-}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT_DIR}/frontend"

npm ci
VITE_API_URL="${API_URL}" npm run build

# Upload the build to web/ (delete removed files).
aws s3 sync dist "s3://${BUCKET}/web" --delete

aws cloudfront create-invalidation \
  --distribution-id "${DISTRIBUTION_ID}" \
  --paths "/*"

echo "Deployed SPA to s3://${BUCKET}/web and invalidated ${DISTRIBUTION_ID}."
