#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
TOKEN="${TOKEN:-}"
ANON_KEY="${ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-public-anon-key}}"
MCP_URL="${MCP_URL:-$BASE_URL/mcp}"
MCP_TOKEN="${MCP_TOKEN:-${STATIC_BEARER_TOKEN:-}}"

if [ -z "$PASSWORD" ] && [ -z "$TOKEN" ]; then
  echo "ERROR: set PASSWORD or TOKEN for API smoke test." >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
API_URL="${API_URL:-$BASE_URL/api}"
API_URL="${API_URL%/}"

echo "== API health =="
curl -fsS "$API_URL/health" >/dev/null || curl -fsS "$API_URL/v1/health" >/dev/null || true

echo "== Login =="
if [ -z "$TOKEN" ]; then
  login_body="$(python3 - "$EMAIL" "$PASSWORD" <<'PY'
import json, sys
print(json.dumps({'email': sys.argv[1], 'password': sys.argv[2]}))
PY
)"
  TOKEN="$(curl -fsS -X POST "$BASE_URL/auth/v1/token?grant_type=password" -H 'Content-Type: application/json' -H "apikey: $ANON_KEY" -d "$login_body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
fi

me="$(curl -fsS "$API_URL/v1/me" -H "Authorization: Bearer $TOKEN")"
printf '%s\n' "$me" | python3 -m json.tool

echo "== Knowledge bases =="
kbs="$(curl -fsS "$API_URL/v1/knowledge-bases" -H "Authorization: Bearer $TOKEN")"
printf '%s\n' "$kbs" | python3 -m json.tool
kb_id="$(KBS="$kbs" python3 - <<'PY'
import json, os
items=json.loads(os.environ['KBS'])
print(items[0]['id'] if items else '')
PY
)"

if [ -n "$kb_id" ]; then
  echo "== Maintenance status =="
  curl -fsS "$API_URL/v1/knowledge-bases/$kb_id/maintenance/status" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
fi

if [ -n "$MCP_TOKEN" ]; then
  echo "== MCP initialize =="
  session_file="/tmp/sovereign-mcp-headers.txt"
  curl -fsS -D "$session_file" -o /tmp/sovereign-mcp-init.json \
    -X POST "$MCP_URL" \
    -H "Authorization: Bearer $MCP_TOKEN" \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"sovereign-smoke","version":"0.1"}}}'
  cat /tmp/sovereign-mcp-init.json
else
  echo "Skipping MCP smoke: set MCP_TOKEN or STATIC_BEARER_TOKEN."
fi

echo "SMOKE_OK"
