#!/usr/bin/env bash
set -euo pipefail

SOVEREIGN_REPO="${SOVEREIGN_REPO:-/opt/sovereign-brain/sovereign-brain-repo}"
LLMWIKI_REPO="${LLMWIKI_REPO:-/opt/sovereign-brain/repos/llmwiki}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.internal-host.yml}"

if [[ ! -d "$SOVEREIGN_REPO/.git" ]]; then
  echo "Missing Sovereign Brain repo: $SOVEREIGN_REPO" >&2
  exit 1
fi

if [[ ! -d "$LLMWIKI_REPO/.git" ]]; then
  echo "Missing LLM Wiki checkout: $LLMWIKI_REPO" >&2
  exit 1
fi

cd "$SOVEREIGN_REPO"
git fetch origin master
git pull --ff-only origin master

rsync -a \
  "$SOVEREIGN_REPO/overlays/llmwiki-web/web/" \
  "$LLMWIKI_REPO/web/"

cp "$SOVEREIGN_REPO/supabase/migrations/006_review_decisions.sql" \
  "$LLMWIKI_REPO/supabase/migrations/006_review_decisions.sql"

cd "$LLMWIKI_REPO"
docker compose -f "$COMPOSE_FILE" build web api mcp
docker compose -f "$COMPOSE_FILE" up -d web api mcp

for path in /brain /brain-review /wikis; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:3030${path}")"
  if [[ "$code" != "200" ]]; then
    echo "Route check failed for ${path}: ${code}" >&2
    exit 1
  fi
done

echo "REBUILD_OK"
