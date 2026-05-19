#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
TOKEN="${TOKEN:-}"
ANON_KEY="${ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-public-anon-key}}"
KB_NAME="${KB_NAME:-Demo Sovereign Brain}"

usage() {
  cat <<USAGE
Usage: BASE_URL=http://host EMAIL=you@example.com PASSWORD=... $0 [options]

Options:
  --base-url URL       Stack origin, default: $BASE_URL
  --email EMAIL        Login email, default: $EMAIL
  --password PASSWORD  Login password
  --token TOKEN        Existing bearer token
  --kb-name NAME       Knowledge base name, default: $KB_NAME
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url) BASE_URL="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    --kb-name) KB_NAME="$2"; shift 2 ;;
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

if [ -z "$TOKEN" ]; then
  login_body="$(python3 - "$EMAIL" "$PASSWORD" <<'PY'
import json, sys
print(json.dumps({"email": sys.argv[1], "password": sys.argv[2]}))
PY
)"
  TOKEN="$(curl -fsS -X POST "$BASE_URL/auth/v1/token?grant_type=password" \
    -H 'Content-Type: application/json' \
    -H "apikey: $ANON_KEY" \
    -d "$login_body" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
fi

kbs="$(curl -fsS "$API_URL/v1/knowledge-bases" -H "Authorization: Bearer $TOKEN")"
kb_id="$(KBS="$kbs" KB_NAME="$KB_NAME" python3 - <<'PY'
import json, os
for kb in json.loads(os.environ["KBS"]):
    if kb.get("name") == os.environ["KB_NAME"] or kb.get("slug") == os.environ["KB_NAME"]:
        print(kb["id"])
        break
PY
)"

if [ -z "$kb_id" ]; then
  echo "ERROR: knowledge base not found: $KB_NAME" >&2
  exit 1
fi

queue="$(curl -fsS "$API_URL/v1/knowledge-bases/$kb_id/maintenance/review-queue" -H "Authorization: Bearer $TOKEN")"

QUEUE="$queue" KB_NAME="$KB_NAME" python3 - <<'PY'
import json, os

data = json.loads(os.environ["QUEUE"])
counts = data.get("review_counts", {})
print(f"# Review Queue: {os.environ['KB_NAME']}")
print()
print(f"- Stale synthesis pages: {counts.get('stale_synthesis_pages', 0)}")
print(f"- Uncited sources: {counts.get('uncited_sources', 0)}")
print(f"- Duplicate active paths: {counts.get('duplicate_active_paths', 0)}")
print()

stale = data.get("stale_synthesis_pages") or []
if stale:
    print("## Stale Synthesis")
    for row in stale:
        print(f"- {row['path']}{row['filename']}")
        print(f"  title: {row.get('title') or ''}")
        print(f"  newest_source_update: {row.get('newest_source_update')}")
        print(f"  newer_source_count: {row.get('newer_source_count', 0)}")
        for source in row.get("linked_sources", [])[:4]:
            excerpt = (source.get("excerpt") or "").replace("\\n", " ").strip()
            print(f"    - source: {source['path']}{source['filename']} ({source.get('updated_at')})")
            if excerpt:
                print(f"      excerpt: {excerpt[:220]}")
    print()

uncited = data.get("uncited_sources") or []
if uncited:
    print("## Uncited Sources")
    for row in uncited[:20]:
        print(f"- {row['path']}{row['filename']} ({row.get('updated_at')})")
        excerpt = (row.get("excerpt") or "").replace("\\n", " ").strip()
        if excerpt:
            print(f"  excerpt: {excerpt[:220]}")
    print()

dupes = data.get("duplicate_active_paths") or []
if dupes:
    print("## Duplicate Paths")
    for row in dupes:
        print(f"- {row['path']}{row['filename']}: {row.get('count')} active copies")
    print()

if not stale and not uncited and not dupes:
    print("Queue is clean.")
PY
