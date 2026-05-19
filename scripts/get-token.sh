#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
ANON_KEY="${ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-public-anon-key}}"

if [ -z "$PASSWORD" ]; then
  echo "ERROR: set PASSWORD." >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
body="$(python3 - "$EMAIL" "$PASSWORD" <<'PY'
import json, sys
print(json.dumps({'email': sys.argv[1], 'password': sys.argv[2]}))
PY
)"

curl -fsS -X POST "$BASE_URL/auth/v1/token?grant_type=password" \
  -H 'Content-Type: application/json' \
  -H "apikey: $ANON_KEY" \
  -d "$body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'
