#!/usr/bin/env bash
set -euo pipefail

SOVEREIGN_REPO="${SOVEREIGN_REPO:-/opt/sovereign-brain/source}"
LLMWIKI_DEPLOY_DIR="${LLMWIKI_DEPLOY_DIR:-/opt/sovereign-brain/llmwiki}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
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

docker build -t sovereign-brain-api:local "$SOVEREIGN_REPO/overlays/api"
docker build -t sovereign-brain-mcp:local "$SOVEREIGN_REPO/overlays/mcp"

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
  UPSTREAM_LLMWIKI_DIR="${UPSTREAM_LLMWIKI_DIR:-}"
  if [[ -n "$UPSTREAM_LLMWIKI_DIR" && -f "$UPSTREAM_LLMWIKI_DIR/$COMPOSE_FILE" ]]; then
    cp "$UPSTREAM_LLMWIKI_DIR/$COMPOSE_FILE" "$LLMWIKI_DEPLOY_DIR/$COMPOSE_FILE"
  else
    echo "Missing compose file: $LLMWIKI_DEPLOY_DIR/$COMPOSE_FILE" >&2
    echo "Set COMPOSE_FILE or place the host-specific compose file in the deploy dir." >&2
    exit 1
  fi
fi

if [[ ! -f "$LLMWIKI_DEPLOY_DIR/.env" && -n "${UPSTREAM_LLMWIKI_DIR:-}" && -f "$UPSTREAM_LLMWIKI_DIR/.env" ]]; then
  cp "$UPSTREAM_LLMWIKI_DIR/.env" "$LLMWIKI_DEPLOY_DIR/.env"
fi

cd "$LLMWIKI_DEPLOY_DIR"
docker compose -f "$COMPOSE_FILE" build web api mcp
docker compose -f "$COMPOSE_FILE" up -d web api mcp

for path in /brain /brain-review /wikis; do
  code=""
  for attempt in {1..30}; do
    code="$(curl -sS -o /dev/null -w "%{http_code}" "http://127.0.0.1:3030${path}" 2>/dev/null || true)"
    if [[ "$code" == "200" ]]; then
      break
    fi
    sleep 1
  done
  if [[ "$code" != "200" ]]; then
    echo "Route check failed for ${path}: ${code:-no response}" >&2
    exit 1
  fi
done

echo "REBUILD_OK"
