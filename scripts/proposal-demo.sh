#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
TOKEN="${TOKEN:-}"
KB_NAME="${KB_NAME:-Demo Sovereign Brain}"
OUT_DIR="${OUT_DIR:-out/review-proposals}"

if [ -z "$PASSWORD" ] && [ -z "$TOKEN" ]; then
  cat >&2 <<ERR
ERROR: set PASSWORD or TOKEN.
Example:
  BASE_URL=http://KOBE_IP EMAIL=admin@example.com PASSWORD='long-random-password' make proposal-demo
ERR
  exit 1
fi

echo "== 1. Baseline demo sync =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/bootstrap-demo.sh >/tmp/sovereign-proposal-demo-baseline.json

echo "== 2. Inject newer source evidence =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" \
  SOURCE_DIR="examples/review-demo/new-sources" \
  SYNTHESIS_DIR="examples/review-demo/no-synthesis" \
  REBUILD_GRAPH=false \
  CHECK_HEALTH=false \
  ./scripts/sovereign-sync.sh >/tmp/sovereign-proposal-demo-inject.txt

echo "== 3. Generate proposal package =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" OUT_DIR="$OUT_DIR" ./scripts/propose-review.sh

echo
echo "== 4. Apply generated proposals =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" OUT_DIR="$OUT_DIR" ./scripts/propose-review.sh --apply

echo
echo "== 5. Health after applying proposals =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/brain-review.sh

echo
echo "Proposal directory: $OUT_DIR"
echo "Review URL: ${BASE_URL%/}/brain-review"
