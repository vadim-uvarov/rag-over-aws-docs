#!/usr/bin/env bash
set -euo pipefail

# Protects the main branch so it can only be updated through pull requests:
#   - no direct pushes to main (a PR is required, admins included)
#   - the PR pipeline must pass before a PR can be merged
#   - all PR conversations must be resolved before a PR can be merged
# Requires the gh CLI, authenticated with admin rights on the repo.

BRANCH="main"

# Status checks that must pass before merging. Keep in sync with the job names
# in .github/workflows/pr.yml.
STATUS_CHECK_CONTEXTS='["lint", "test", "commitizen", "terraform"]'

if ! command -v gh >/dev/null 2>&1; then
  echo "Error: the GitHub CLI (gh) is required." >&2
  exit 1
fi

DEFAULT_REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
read -r -p "GitHub repository (owner/name)${DEFAULT_REPO:+ [$DEFAULT_REPO]}: " REPO
REPO="${REPO:-$DEFAULT_REPO}"
if [ -z "$REPO" ]; then
  echo "Error: repository is required (owner/name)." >&2
  exit 1
fi

# The branch must exist before it can be protected (push an initial commit first).
if ! gh api "repos/${REPO}/branches/${BRANCH}" >/dev/null 2>&1; then
  echo "Error: branch '${BRANCH}' not found in ${REPO}. Push it first." >&2
  exit 1
fi

echo "Protecting ${REPO}@${BRANCH} ..."

# required_pull_request_reviews (even with 0 approvals) enables "require a pull
# request before merging", which is what blocks direct pushes. Set strict=true
# below to additionally require branches be up to date before merging.
gh api --method PUT "repos/${REPO}/branches/${BRANCH}/protection" \
  --header "Accept: application/vnd.github+json" \
  --input - <<JSON
{
  "required_status_checks": {
    "strict": false,
    "contexts": ${STATUS_CHECK_CONTEXTS}
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews": false,
    "require_code_owner_reviews": false
  },
  "restrictions": null,
  "required_conversation_resolution": true,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

echo "Done. '${BRANCH}' now requires a passing PR with all conversations resolved to merge."
