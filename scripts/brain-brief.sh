#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
TOKEN="${TOKEN:-}"
ANON_KEY="${ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-public-anon-key}}"
KB_NAME="${KB_NAME:-Demo Sovereign Brain}"
OUT_DIR="${OUT_DIR:-out/brain-briefs}"
LEDGER_ROOT="${LEDGER_ROOT:-out/review-proposals}"

usage() {
  cat <<USAGE
Usage: BASE_URL=http://host EMAIL=you@example.com PASSWORD=... $0 [options]

Options:
  --base-url URL       Stack origin, default: $BASE_URL
  --email EMAIL        Login email, default: $EMAIL
  --password PASSWORD  Login password
  --token TOKEN        Existing bearer token
  --kb-name NAME       Knowledge base name or slug, default: $KB_NAME
  --out-dir DIR        Brief output directory, default: $OUT_DIR
  --ledger-root DIR    Proposal ledger root, default: $LEDGER_ROOT
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-url) BASE_URL="$2"; shift 2 ;;
    --email) EMAIL="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    --kb-name) KB_NAME="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --ledger-root) LEDGER_ROOT="$2"; shift 2 ;;
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
kb_json="$(KBS="$kbs" KB_NAME="$KB_NAME" python3 - <<'PY'
import json, os
for kb in json.loads(os.environ["KBS"]):
    if kb.get("name") == os.environ["KB_NAME"] or kb.get("slug") == os.environ["KB_NAME"]:
        print(json.dumps(kb))
        break
PY
)"

if [ -z "$kb_json" ]; then
  echo "ERROR: knowledge base not found: $KB_NAME" >&2
  exit 1
fi

kb_id="$(printf '%s' "$kb_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
status="$(curl -fsS "$API_URL/v1/knowledge-bases/$kb_id/maintenance/status" -H "Authorization: Bearer $TOKEN")"
queue="$(curl -fsS "$API_URL/v1/knowledge-bases/$kb_id/maintenance/review-queue" -H "Authorization: Bearer $TOKEN")"

STATUS="$status" QUEUE="$queue" KB_JSON="$kb_json" OUT_DIR="$OUT_DIR" LEDGER_ROOT="$LEDGER_ROOT" python3 - <<'PY'
import datetime as dt
import json
import os
import pathlib

status = json.loads(os.environ["STATUS"])
queue = json.loads(os.environ["QUEUE"])
kb = json.loads(os.environ["KB_JSON"])
out_dir = pathlib.Path(os.environ["OUT_DIR"]) / kb["slug"]
ledger_path = pathlib.Path(os.environ["LEDGER_ROOT"]) / kb["slug"] / "review-decisions.jsonl"
out_dir.mkdir(parents=True, exist_ok=True)


def count(name):
    return int((queue.get("review_counts") or {}).get(name, 0) or 0)


def ts(value):
    return str(value or "?").replace("T", " ")[:19]


ledger_entries = []
if ledger_path.exists():
    for line in ledger_path.read_text(encoding="utf-8").splitlines()[-12:]:
        if line.strip():
            try:
                ledger_entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass

summary = status.get("summary") or {}
stale = queue.get("stale_synthesis_pages") or []
uncited = queue.get("uncited_sources") or []
dupes = queue.get("duplicate_active_paths") or []
recent = status.get("recent_changes") or []
trust_ok = count("stale_synthesis_pages") == 0 and count("duplicate_active_paths") == 0

lines = [
    f"# Brain Brief: {kb['name']}",
    "",
    f"Generated: `{dt.datetime.now(dt.timezone.utc).isoformat()}`",
    "",
    f"## Trust Status: {'Healthy' if trust_ok else 'Needs Review'}",
    "",
    f"- Active documents: `{summary.get('active_documents', 0)}`",
    f"- Source documents: `{summary.get('source_documents', 0)}`",
    f"- Wiki pages: `{summary.get('wiki_pages', 0)}`",
    f"- Synthesis pages: `{summary.get('synthesis_pages', 0)}`",
    f"- Reference edges: `{status.get('reference_edges', 0)}`",
    f"- Stale synthesis pages: `{count('stale_synthesis_pages')}`",
    f"- Uncited sources: `{count('uncited_sources')}`",
    f"- Duplicate active paths: `{count('duplicate_active_paths')}`",
    "",
    "## What Changed",
    "",
]

if recent:
    for row in recent[:8]:
        lines.append(f"- `{row.get('path', '')}{row.get('filename', '')}` ({row.get('kind', '?')}) updated `{ts(row.get('updated_at'))}`")
else:
    lines.append("- No recent changes reported.")

lines += ["", "## What Needs Attention", ""]
if stale:
    for row in stale[:8]:
        lines.append(f"- Review stale synthesis `{row['path']}{row['filename']}`; newest source `{ts(row.get('newest_source_update'))}`.")
elif dupes:
    lines.append("- Resolve duplicate active paths before trusting the brain.")
else:
    lines.append("- No stale synthesis or duplicate paths currently block trust.")

if uncited:
    lines += ["", "## Uncited Source Candidates", ""]
    for row in uncited[:8]:
        lines.append(f"- `{row['path']}{row['filename']}` updated `{ts(row.get('updated_at'))}`")

lines += ["", "## Proposal / Ledger Activity", ""]
if ledger_entries:
    for entry in ledger_entries[-8:]:
        lines.append(
            f"- `{entry.get('action')}` `{entry.get('synthesis_path')}` by `{entry.get('actor')}` "
            f"at `{ts(entry.get('timestamp'))}` hash `{str(entry.get('proposal_sha256', ''))[:12]}`"
        )
else:
    lines.append("- No local proposal ledger entries found.")

lines += ["", "## Recommended Next Action", ""]
if stale:
    lines.append("- Run `make propose`, inspect the generated diff, then apply only after review.")
elif uncited:
    lines.append("- Triage uncited sources and decide whether they should update synthesis or stay as raw evidence.")
elif ledger_entries:
    lines.append("- Brain is currently healthy. Use the latest ledger entries as audit proof for recent repairs.")
else:
    lines.append("- Brain is currently healthy. Keep source sync and maintenance checks running.")

brief = "\n".join(lines) + "\n"
path = out_dir / "brain-brief.md"
json_path = out_dir / "brain-brief.json"
path.write_text(brief, encoding="utf-8")
json_path.write_text(json.dumps({
    "knowledge_base": kb,
    "trust_status": "healthy" if trust_ok else "needs_review",
    "status": status,
    "queue": queue,
    "ledger_entries": ledger_entries,
    "brief_path": str(path),
}, indent=2), encoding="utf-8")
print(brief)
print(f"Wrote {path}")
print(f"Wrote {json_path}")
PY
