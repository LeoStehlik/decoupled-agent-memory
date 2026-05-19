#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
TOKEN="${TOKEN:-}"
KB_NAME="${KB_NAME:-Demo Sovereign Brain}"
OUT_DIR="${OUT_DIR:-out/review-proposals}"
ACTOR="${ACTOR:-ledger-demo}"

if [ -z "$PASSWORD" ] && [ -z "$TOKEN" ]; then
  cat >&2 <<ERR
ERROR: set PASSWORD or TOKEN.
Example:
  BASE_URL=http://KOBE_IP EMAIL=admin@example.com PASSWORD='long-random-password' make ledger-demo
ERR
  exit 1
fi

echo "== 1. Baseline demo sync =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/bootstrap-demo.sh >/tmp/sovereign-ledger-demo-baseline.json

echo "== 2. Inject newer source evidence =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" \
  SOURCE_DIR="examples/review-demo/new-sources" \
  SYNTHESIS_DIR="examples/review-demo/no-synthesis" \
  REBUILD_GRAPH=false \
  CHECK_HEALTH=false \
  ./scripts/sovereign-sync.sh >/tmp/sovereign-ledger-demo-inject.txt

echo "== 3. Propose with diff + ledger entry =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" OUT_DIR="$OUT_DIR" ACTOR="$ACTOR" \
  ./scripts/propose-review.sh --rationale "Ledger demo proposal from newer source evidence."

echo
echo "== 4. Apply with explicit ledger entry =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" OUT_DIR="$OUT_DIR" ACTOR="$ACTOR" \
  ./scripts/propose-review.sh --apply --rationale "Ledger demo accepted proposal after source-backed review."

echo
echo "== 5. Health after accepted proposals =="
BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" TOKEN="$TOKEN" KB_NAME="$KB_NAME" ./scripts/brain-review.sh

ledger_path="$(find "$OUT_DIR" -mindepth 2 -maxdepth 2 -name review-decisions.jsonl -print | sort | tail -1)"

echo
echo "== 6. Acceptance ledger =="
if [ -n "$ledger_path" ] && [ -f "$ledger_path" ]; then
  tail -20 "$ledger_path"
else
  echo "Ledger not found under: $OUT_DIR" >&2
  exit 1
fi

echo
echo "Proposal directory: $OUT_DIR"
echo "Ledger: $ledger_path"
echo "Review URL: ${BASE_URL%/}/brain-review"
