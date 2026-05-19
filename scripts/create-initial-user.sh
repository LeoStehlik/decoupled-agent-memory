#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.invalid}"
PASSWORD="${PASSWORD:-}"
DISPLAY_NAME="${DISPLAY_NAME:-Admin}"
ANON_KEY="${ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-public-anon-key}}"
COMPLETE_ONBOARDING="${COMPLETE_ONBOARDING:-true}"

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
  printf '\nSignup did not create a new user. Trying password login in case the user already exists.\n' >&2
else
  printf '%s' "$signup_response" | python3 -m json.tool >/tmp/create-initial-user-signup.json
fi

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

token="$(LOGIN_RESPONSE="$login_response" python3 - <<'PY'
import json, os, sys
payload=json.loads(os.environ['LOGIN_RESPONSE'])
token=payload.get('access_token')
user=payload.get('user') or {}
if not token:
    raise SystemExit('Login did not return access_token')
print(f"OK: login verified for {user.get('email', '<unknown>')}", file=sys.stderr)
print(token)
PY
)"

case "$COMPLETE_ONBOARDING" in
  true|1|yes|YES|y|Y)
    curl -fsS -X POST "$BASE_URL/api/v1/onboarding/complete" \
      -H "Authorization: Bearer $token" \
      -H 'Content-Type: application/json' \
      -d '{}' >/dev/null
    me_response="$(curl -fsS "$BASE_URL/api/v1/me" -H "Authorization: Bearer $token")"
    ME_RESPONSE="$me_response" python3 - <<'PY'
import json, os
payload=json.loads(os.environ['ME_RESPONSE'])
if not payload.get('onboarded'):
    raise SystemExit('User login works, but onboarding verification failed')
print(f"OK: onboarding complete for {payload.get('email', '<unknown>')}")
PY
    ;;
  *)
    printf 'Skipping onboarding completion because COMPLETE_ONBOARDING=%s\n' "$COMPLETE_ONBOARDING" >&2
    ;;
esac

printf '\nNext recommended hardening step for private deployments:\n  set GOTRUE_DISABLE_SIGNUP=true in .env and run docker compose up -d\n' >&2
