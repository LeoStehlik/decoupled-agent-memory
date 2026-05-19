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
  BASE_URL=http://KOBE_IP EMAIL=admin@example.com PASSWORD='long-random-password' make brief-demo
ERR
  exit 1
fi

echo "== 1. Baseline demo sync =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/bootstrap-demo.sh >/tmp/sovereign-brief-demo-baseline.json

echo "== 2. Inject newer source evidence =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" \
  SOURCE_DIR="examples/review-demo/new-sources" \
  SYNTHESIS_DIR="examples/review-demo/no-synthesis" \
  REBUILD_GRAPH=false \
  CHECK_HEALTH=false \
  ./scripts/sovereign-sync.sh >/tmp/sovereign-brief-demo-inject.txt

echo "== 3. Brief while review is needed =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/brain-brief.sh

echo
echo "== 4. Repair through ledger path =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ACTOR="brief-demo" ./scripts/propose-review.sh --apply --rationale "Brief demo accepted source-backed proposal."

echo
echo "== 5. Brief after repair =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/brain-brief.sh

echo
echo "Brief URL: ${BASE_URL%/}/brain-brief"
