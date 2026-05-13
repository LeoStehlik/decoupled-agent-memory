#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.invalid}"
PASSWORD="${PASSWORD:-}"
DISPLAY_NAME="${DISPLAY_NAME:-Admin}"
ANON_KEY="${ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-public-anon-key}}"

if [ -z "$PASSWORD" ]; then
  printf 'ERROR: set PASSWORD, for example:\n  PASSWORD="change-me-long-random-password" %s\n' "$0" >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"

signup_json="$(python3 - "$EMAIL" "$PASSWORD" "$DISPLAY_NAME" <<'PY'
import json, sys
email, password, display_name = sys.argv[1:4]
print(json.dumps({"email": email, "password": password, "data": {"display_name": display_name}}))
PY
)"

login_json="$(python3 - "$EMAIL" "$PASSWORD" <<'PY'
import json, sys
email, password = sys.argv[1:3]
print(json.dumps({"email": email, "password": password}))
PY
)"

printf 'Creating initial user %s at %s...\n' "$EMAIL" "$BASE_URL" >&2
signup_response="$({
  curl -fsS -X POST "$BASE_URL/auth/v1/signup" \
    -H 'Content-Type: application/json' \
    -H "apikey: $ANON_KEY" \
    -d "$signup_json"
} 2>/tmp/create-initial-user-curl.err || true)"

if [ -z "$signup_response" ]; then
  cat /tmp/create-initial-user-curl.err >&2 || true
  printf '\nSignup failed. If you disabled signup, temporarily set GOTRUE_DISABLE_SIGNUP=false, restart, run this script, then disable signup again.\n' >&2
  exit 1
fi

printf '%s' "$signup_response" | python3 -m json.tool >/tmp/create-initial-user-signup.json

login_response="$({
  curl -fsS -X POST "$BASE_URL/auth/v1/token?grant_type=password" \
    -H 'Content-Type: application/json' \
    -H "apikey: $ANON_KEY" \
    -d "$login_json"
} 2>/tmp/create-initial-user-login.err || true)"

if [ -z "$login_response" ]; then
  cat /tmp/create-initial-user-login.err >&2 || true
  printf '\nUser was submitted, but login verification failed. Check auth logs with: docker compose logs supabase-auth\n' >&2
  exit 1
fi

LOGIN_RESPONSE="$login_response" python3 - <<'PY'
import json, os
payload=json.loads(os.environ['LOGIN_RESPONSE'])
token=payload.get('access_token')
user=payload.get('user') or {}
if not token:
    raise SystemExit('Login did not return access_token')
print(f"OK: login verified for {user.get('email', '<unknown>')}")
PY

printf '\nNext recommended hardening step for private deployments:\n  set GOTRUE_DISABLE_SIGNUP=true in .env and run docker compose up -d\n' >&2
