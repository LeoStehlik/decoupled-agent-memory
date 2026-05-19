#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
EMAIL="${EMAIL:-admin@example.com}"
PASSWORD="${PASSWORD:-}"
TOKEN="${TOKEN:-}"
ANON_KEY="${ANON_KEY:-${NEXT_PUBLIC_SUPABASE_ANON_KEY:-public-anon-key}}"
KB_NAME="${KB_NAME:-Demo Sovereign Brain}"
OUT_DIR="${OUT_DIR:-out/review-proposals}"
ACTOR="${ACTOR:-operator}"
RATIONALE="${RATIONALE:-Generated from stale synthesis review queue.}"
APPLY=false

usage() {
  cat <<USAGE
Usage: BASE_URL=http://host EMAIL=you@example.com PASSWORD=... $0 [options]

Options:
  --base-url URL       Stack origin, default: $BASE_URL
  --email EMAIL        Login email, default: $EMAIL
  --password PASSWORD  Login password
  --token TOKEN        Existing bearer token
  --kb-name NAME       Knowledge base name or slug, default: $KB_NAME
  --out-dir DIR        Proposal output directory, default: $OUT_DIR
  --actor NAME         Ledger actor, default: $ACTOR
  --rationale TEXT     Ledger rationale
  --apply             Apply generated proposals back to stale synthesis pages
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
    --actor) ACTOR="$2"; shift 2 ;;
    --rationale) RATIONALE="$2"; shift 2 ;;
    --apply) APPLY=true; shift ;;
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
queue="$(curl -fsS "$API_URL/v1/knowledge-bases/$kb_id/maintenance/review-queue" -H "Authorization: Bearer $TOKEN")"

QUEUE="$queue" KB_JSON="$kb_json" TOKEN="$TOKEN" API_URL="$API_URL" OUT_DIR="$OUT_DIR" APPLY="$APPLY" ACTOR="$ACTOR" RATIONALE="$RATIONALE" python3 - <<'PY'
import datetime as dt
import difflib
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

queue = json.loads(os.environ["QUEUE"])
kb = json.loads(os.environ["KB_JSON"])
token = os.environ["TOKEN"]
api_url = os.environ["API_URL"].rstrip("/")
out_root = pathlib.Path(os.environ["OUT_DIR"]) / kb["slug"]
apply = os.environ["APPLY"].lower() == "true"
actor = os.environ["ACTOR"]
rationale = os.environ["RATIONALE"]
out_root.mkdir(parents=True, exist_ok=True)


def request_json(method, path, body=None):
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{api_url}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {path} failed: HTTP {exc.code} {exc.read().decode(errors='replace')}")
    return json.loads(raw.decode() or "{}")


def slug(value):
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-") or "proposal"


def strip_frontmatter(text):
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:].lstrip()
    return text


def source_link(row):
    return f"{row['path']}{row['filename']}"


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def append_ledger(path, entry):
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


stale = queue.get("stale_synthesis_pages") or []
ledger_path = out_root / "review-decisions.jsonl"
manifest = {
    "knowledge_base": {"id": kb["id"], "name": kb["name"], "slug": kb["slug"]},
    "proposal_count": 0,
    "applied": apply,
    "ledger_path": str(ledger_path),
    "proposals": [],
}

if not stale:
    print(f"No stale synthesis pages in {kb['name']}.")
    manifest_path = out_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {manifest_path}")
    sys.exit(0)

for row in stale:
    page_content = request_json("GET", f"/v1/documents/{row['id']}/content").get("content") or ""
    linked_sources = []
    for src in row.get("linked_sources", []):
        full = request_json("GET", f"/v1/documents/{src['id']}/content").get("content") or ""
        src = dict(src)
        src["content"] = full
        linked_sources.append(src)

    evidence_lines = []
    source_sections = []
    for index, src in enumerate(linked_sources, start=1):
        link = source_link(src)
        title = src.get("title") or src["filename"]
        evidence_lines.append(f"- [{title}](../../{src['filename']}) updated `{src.get('updated_at')}`")
        body = strip_frontmatter(src["content"]).strip()
        excerpt = body[:1600].strip()
        source_sections.append(f"### Source {index}: {title}\n\nPath: `{link}`\n\n{excerpt}")

    proposal = page_content.rstrip() + "\n\n"
    proposal += "## Proposed Review Update\n\n"
    proposal += "This section is a generated proposal from the current review queue. Review it before treating the synthesis as current.\n\n"
    proposal += "### Change Rationale\n\n"
    proposal += f"- `{row['path']}{row['filename']}` is stale because linked source evidence is newer than the synthesis page.\n"
    proposal += f"- Newest linked source update: `{row.get('newest_source_update')}`.\n"
    proposal += "- The maintained synthesis should incorporate the changed evidence or explicitly record why it was ignored.\n\n"
    proposal += "### Evidence Reviewed\n\n" + "\n".join(evidence_lines) + "\n\n"
    proposal += "### Draft Maintenance Note\n\n"
    proposal += "The linked source evidence has changed since this synthesis was last reviewed. Update the conclusions above where the evidence changes the current operating position, then remove or fold this proposal section into the maintained page.\n\n"
    proposal += "## Source Evidence Snapshot\n\n" + "\n\n".join(source_sections) + "\n"

    filename = slug(row["filename"].rsplit(".", 1)[0]) + ".proposal.md"
    proposal_path = out_root / filename
    diff_path = out_root / (filename + ".diff.md")
    meta_path = out_root / (filename + ".json")
    proposal_path.write_text(proposal, encoding="utf-8")
    diff_lines = difflib.unified_diff(
        page_content.splitlines(),
        proposal.splitlines(),
        fromfile=f"original/{row['path']}{row['filename']}",
        tofile=f"proposal/{row['path']}{row['filename']}",
        lineterm="",
    )
    diff_text = "\n".join(diff_lines) + "\n"
    diff_path.write_text(diff_text, encoding="utf-8")
    proposal_hash = sha256(proposal)
    meta = {
        "status": "applied" if apply else "proposed",
        "synthesis_document_id": row["id"],
        "synthesis_path": f"{row['path']}{row['filename']}",
        "proposal_path": str(proposal_path),
        "diff_path": str(diff_path),
        "proposal_sha256": proposal_hash,
        "newest_source_update": row.get("newest_source_update"),
        "linked_sources": [
            {
                "id": src["id"],
                "path": source_link(src),
                "title": src.get("title"),
                "updated_at": src.get("updated_at"),
            }
            for src in linked_sources
        ],
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    ledger_entry = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "knowledge_base": {"id": kb["id"], "name": kb["name"], "slug": kb["slug"]},
        "synthesis_document_id": row["id"],
        "synthesis_path": f"{row['path']}{row['filename']}",
        "proposal_path": str(proposal_path),
        "diff_path": str(diff_path),
        "proposal_sha256": proposal_hash,
        "linked_source_ids": [src["id"] for src in linked_sources],
        "linked_sources": [
            {
                "id": src["id"],
                "path": source_link(src),
                "title": src.get("title"),
                "updated_at": src.get("updated_at"),
            }
            for src in linked_sources
        ],
        "action": "applied" if apply else "proposed",
        "actor": actor,
        "rationale": rationale,
    }
    if apply:
        request_json("PUT", f"/v1/documents/{row['id']}/content", {"content": proposal})
    append_ledger(ledger_path, ledger_entry)
    manifest["proposal_count"] += 1
    manifest["proposals"].append(meta)
    print(f"{'applied' if apply else 'proposed'} {row['path']}{row['filename']} -> {proposal_path}")
    print(f"diff {diff_path}")

manifest_path = out_root / "manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(f"Wrote {manifest_path}")
print(f"Ledger {ledger_path}")
PY
