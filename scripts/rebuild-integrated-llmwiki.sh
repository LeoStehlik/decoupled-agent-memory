#!/usr/bin/env bash
set -euo pipefail

SOVEREIGN_REPO="${SOVEREIGN_REPO:-/opt/sovereign-brain/sovereign-brain-repo}"
LLMWIKI_DEPLOY_DIR="${LLMWIKI_DEPLOY_DIR:-/opt/sovereign-brain/sovereign-brain-llmwiki}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.internal-host.yml}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-llmwiki}"

if [[ ! -d "$SOVEREIGN_REPO/.git" ]]; then
  echo "Missing Sovereign Brain repo: $SOVEREIGN_REPO" >&2
  exit 1
fi

cd "$SOVEREIGN_REPO"
git fetch origin master
git pull --ff-only origin master

if [[ ! -d "$SOVEREIGN_REPO/llmwiki-app" ]]; then
  echo "Missing in-repo LLM Wiki app source: $SOVEREIGN_REPO/llmwiki-app" >&2
  exit 1
fi

mkdir -p "$LLMWIKI_DEPLOY_DIR"
rsync -a --delete \
  --exclude .git \
  --exclude .env \
  --exclude ".env.*" \
  --exclude "node_modules/" \
  --exclude ".next/" \
  "$SOVEREIGN_REPO/llmwiki-app/" \
  "$LLMWIKI_DEPLOY_DIR/"

if [[ ! -f "$LLMWIKI_DEPLOY_DIR/$COMPOSE_FILE" ]]; then
  if [[ -f "/opt/sovereign-brain/repos/llmwiki/$COMPOSE_FILE" ]]; then
    cp "/opt/sovereign-brain/repos/llmwiki/$COMPOSE_FILE" "$LLMWIKI_DEPLOY_DIR/$COMPOSE_FILE"
  else
    echo "Missing compose file: $LLMWIKI_DEPLOY_DIR/$COMPOSE_FILE" >&2
    echo "Set COMPOSE_FILE or place the host-specific compose file in the deploy dir." >&2
    exit 1
  fi
fi

if [[ ! -f "$LLMWIKI_DEPLOY_DIR/.env" && -f "/opt/sovereign-brain/repos/llmwiki/.env" ]]; then
  cp "/opt/sovereign-brain/repos/llmwiki/.env" "$LLMWIKI_DEPLOY_DIR/.env"
fi

cd "$LLMWIKI_DEPLOY_DIR"
docker compose -f "$COMPOSE_FILE" build web api mcp
docker compose -f "$COMPOSE_FILE" up -d web api mcp

for path in /brain /brain-review /wikis; do
  code="$(curl -sS -o /dev/null -w %{http_code} "http://127.0.0.1:3030${path}")"
  if [[ "$code" != "200" ]]; then
    echo "Route check failed for ${path}: ${code}" >&2
    exit 1
  fi
done

echo "REBUILD_OK"
