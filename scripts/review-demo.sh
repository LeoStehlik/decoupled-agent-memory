#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
TOKEN="${TOKEN:-}"
KB_NAME="${KB_NAME:-Demo Sovereign Brain}"

if [ -z "$PASSWORD" ] && [ -z "$TOKEN" ]; then
  cat >&2 <<ERR
ERROR: set PASSWORD or TOKEN.
Example:
  BASE_URL=http://INTERNAL_HOST EMAIL=admin@example.com PASSWORD='long-random-password' make review-demo
ERR
  exit 1
fi

echo "== 1. Baseline demo sync =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/bootstrap-demo.sh >/tmp/sovereign-review-demo-baseline.json

echo "== 2. Inject newer source evidence =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" \
  SOURCE_DIR="examples/review-demo/new-sources" \
  SYNTHESIS_DIR="examples/review-demo/no-synthesis" \
  REBUILD_GRAPH=false \
  CHECK_HEALTH=false \
  ./scripts/sovereign-sync.sh >/tmp/sovereign-review-demo-inject.txt

echo "== 3. Review queue after source change =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/brain-review.sh

echo
echo "== 4. Apply reviewed synthesis update =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" \
  SOURCE_DIR="examples/review-demo/no-sources" \
  SYNTHESIS_DIR="examples/review-demo/reviewed-synthesis" \
  REBUILD_GRAPH=false \
  CHECK_HEALTH=true \
  ./scripts/sovereign-sync.sh

echo
echo "Review URL: ${BASE_URL%/}/brain-review"
