#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
TOKEN="${TOKEN:-}"
ANON_KEY="${ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-public-anon-key}}"
KB_NAME="${KB_NAME:-Demo Sovereign Brain}"
SOURCE_DIR="${SOURCE_DIR:-examples/demo-corpus/sources}"
SYNTHESIS_DIR="${SYNTHESIS_DIR:-examples/demo-corpus/synthesis}"
REBUILD_GRAPH="${REBUILD_GRAPH:-true}"
CHECK_HEALTH="${CHECK_HEALTH:-true}"

usage() {
  cat <<USAGE
Usage: BASE_URL=http://host EMAIL=you@example.com PASSWORD=... $0 [options]

Options:
  --base-url URL       Stack origin, default: $BASE_URL
  --email EMAIL        Login email, default: $EMAIL
  --password PASSWORD  Login password
  --kb-name NAME       Knowledge base name, default: $KB_NAME
  --source-dir DIR     Markdown source directory, default: $SOURCE_DIR
  --synthesis-dir DIR  Markdown synthesis directory, default: $SYNTHESIS_DIR
  --no-rebuild-graph   Skip graph rebuild
  --no-health          Skip maintenance-status check
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url) BASE_URL="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    --kb-name) KB_NAME="$2"; shift 2 ;;
    --source-dir) SOURCE_DIR="$2"; shift 2 ;;
    --synthesis-dir) SYNTHESIS_DIR="$2"; shift 2 ;;
    --no-rebuild-graph) REBUILD_GRAPH=false; shift ;;
    --no-health) CHECK_HEALTH=false; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$PASSWORD" ] && [ -z "$TOKEN" ]; then
  echo "ERROR: set PASSWORD or TOKEN." >&2
  exit 1
fi

BASE_URL="${BASE_URL%/}"
API_URL="${API_URL:-$BASE_URL/api}"
API_URL="${API_URL%/}"

json_escape_file() {
  python3 - "$1" <<'PY'
import json, pathlib, sys
print(json.dumps(pathlib.Path(sys.argv[1]).read_text()))
PY
}

json_escape_arg() {
  python3 - "$1" <<'PY'
import json, sys
print(json.dumps(sys.argv[1]))
PY
}

api() {
  local method="$1" path="$2" body="${3:-}"
  if [ -n "$body" ]; then
    curl -fsS -X "$method" "$API_URL$path" \
      -H "Authorization: Bearer $TOKEN" \
      -H 'Content-Type: application/json' \
      -d "$body"
  else
    curl -fsS -X "$method" "$API_URL$path" \
      -H "Authorization: Bearer $TOKEN"
  fi
}

if [ -z "$TOKEN" ]; then
  login_body="$(python3 - "$EMAIL" "$PASSWORD" <<'PY'
import json, sys
print(json.dumps({'email': sys.argv[1], 'password': sys.argv[2]}))
PY
)"
  TOKEN="$(curl -fsS -X POST "$BASE_URL/auth/v1/token?grant_type=password" \
    -H 'Content-Type: application/json' \
    -H "apikey: $ANON_KEY" \
    -d "$login_body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
fi

kb_body="$(python3 - "$KB_NAME" <<'PY'
import json, sys
print(json.dumps({'name': sys.argv[1], 'description': 'Demo private memory layer with source-backed synthesis and freshness checks.'}))
PY
)"
KB_JSON="$(api POST /v1/knowledge-bases "$kb_body")"
KB_ID="$(printf '%s' "$KB_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
KB_SLUG="$(printf '%s' "$KB_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["slug"])')"
printf 'Sync target: %s (%s)\n' "$KB_NAME" "$KB_SLUG" >&2

upsert_note() {
  local file="$1" path="$2" filename content body docs doc_id
  filename="$(basename "$file")"
  content="$(json_escape_file "$file")"
  docs="$(api GET "/v1/knowledge-bases/$KB_ID/documents?path=$(python3 - "$path" <<'PY'
import urllib.parse, sys
print(urllib.parse.quote(sys.argv[1], safe=''))
PY
)")"
  doc_id="$(DOCS="$docs" FILENAME="$filename" python3 - <<'PY'
import json, os
for row in json.loads(os.environ['DOCS']):
    if row.get('filename') == os.environ['FILENAME']:
        print(row['id'])
        break
PY
)"
  if [ -n "$doc_id" ]; then
    body="{\"content\":$content}"
    api PUT "/v1/documents/$doc_id/content" "$body" >/dev/null
    printf 'updated %s%s\n' "$path" "$filename" >&2
  else
    body="{\"filename\":$(json_escape_arg "$filename"),\"path\":$(json_escape_arg "$path"),\"content\":$content}"
    api POST "/v1/knowledge-bases/$KB_ID/documents/note" "$body" >/dev/null
    printf 'created %s%s\n' "$path" "$filename" >&2
  fi
}

if [ -d "$SOURCE_DIR" ]; then
  find "$SOURCE_DIR" -type f -name '*.md' | sort | while read -r file; do
    upsert_note "$file" "/"
  done
fi

if [ -d "$SYNTHESIS_DIR" ]; then
  find "$SYNTHESIS_DIR" -type f -name '*.md' | sort | while read -r file; do
    upsert_note "$file" "/wiki/synthesis/"
  done
fi

if [ "$REBUILD_GRAPH" = true ]; then
  if ! api POST "/v1/knowledge-bases/$KB_ID/graph/rebuild" '{}' >/tmp/sovereign-sync-graph.json 2>/tmp/sovereign-sync-graph.err; then
    if rg -q 'cooldown|429' /tmp/sovereign-sync-graph.err; then
      echo 'Graph rebuild skipped: cooldown active.' >&2
    else
      cat /tmp/sovereign-sync-graph.err >&2
      exit 1
    fi
  else
    printf 'Graph rebuild: %s\n' "$(cat /tmp/sovereign-sync-graph.json)" >&2
  fi
fi

if [ "$CHECK_HEALTH" = true ]; then
  api GET "/v1/knowledge-bases/$KB_ID/maintenance/status" | python3 -m json.tool
fi

cat <<OUT

Demo URLs:
- Wiki: $BASE_URL/wikis/$KB_SLUG/wiki/overview.md
- Health: $BASE_URL/brain-health
OUT
