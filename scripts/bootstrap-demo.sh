#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
DISPLAY_NAME="${DISPLAY_NAME:-Admin}"
KB_NAME="${KB_NAME:-Demo Sovereign Brain}"

if [ -z "$PASSWORD" ]; then
  cat >&2 <<ERR
ERROR: set PASSWORD for the demo user.
Example:
  BASE_URL=http://INTERNAL_HOST EMAIL=admin@example.com PASSWORD='long-random-password' make demo
ERR
  exit 1
fi

BASE_URL="${BASE_URL%/}"

if ! BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" DISPLAY_NAME="$DISPLAY_NAME" ./scripts/create-initial-user.sh; then
  echo "Initial user creation did not complete. If the user already exists, continuing with login/sync." >&2
fi

BASE_URL="$BASE_URL" EMAIL="$EMAIL" PASSWORD="$PASSWORD" KB_NAME="$KB_NAME" \
  SOURCE_DIR="examples/demo-corpus/sources" \
  SYNTHESIS_DIR="examples/demo-corpus/synthesis" \
  ./scripts/sovereign-sync.sh
