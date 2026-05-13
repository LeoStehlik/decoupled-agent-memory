# Sovereign Brain

A private, internal-perimeter blueprint for deploying a durable agent memory layer based on the LLM Wiki pattern.

## Attribution

This repository is an internal-only deployment blueprint derived from **Andrej Karpathy's LLM Wiki** pattern and the open-source implementation by **Lucas Astorian** at `lucasastorian/llmwiki` (`https://github.com/lucasastorian/llmwiki`). Keep that credit prominent in downstream reuse. This repo adapts that pattern for a private internal host-hosted deployment with simplified internal routing and sanitised placeholders.

## What this repo is

This is **not** a public SaaS template.
It is a blueprint for a private stack that runs inside a trusted network perimeter, for example:

- internal client or remote client on the same private network
- internal host as the internal server
- Nginx routing traffic only between internal services
- Postgres plus auth plus API plus MCP kept on the private side

The point is simple: agents should stop rebuilding context from raw files every time, and instead write into a maintained memory layer that compounds over time.

## Why this exists

Most agent systems pay a hidden context tax:

- they repeatedly reread the same source material
- synthesis is recreated instead of maintained
- contradictions stay buried
- link graphs never stabilise
- token spend rises while confidence stays shaky

A Sovereign Brain reduces that tax with three layers:

1. **Raw sources**: notes, PDFs, transcripts, markdown, HTML, screenshots, exports
2. **Compiled knowledge**: wiki pages, entity notes, summaries, contradiction logs, timelines
3. **Agent access layer**: API and MCP surfaces for search, read, write, maintenance

## Included here

- `docker-compose.yml` for the internal stack
- pre-built GHCR images for faster startup: `ghcr.io/leostehlik/llm-wiki-web:latest`, `ghcr.io/leostehlik/llm-wiki-api:latest`, and `ghcr.io/leostehlik/llm-wiki-mcp:latest`
- `infra/nginx/conf.d/llm-wiki.conf` for the internal edge router
- `infra/supabase/nginx.conf` for the auth proxy and the CORS/header fixes
- `setup-guide.md` and `docs/setup-guide.md` for deployment on internal host
- `architecture.md` and `docs/architecture.md` for system shape and data flow
- `.env.example` with sanitised placeholders only

## Core components

| Component | Role |
| --- | --- |
| `db` | Postgres persistence for documents, wiki pages, auth data |
| `supabase-auth` | GoTrue auth service |
| `supabase-proxy` | Internal auth proxy with preflight handling and header cleanup |
| `api` | Ingestion, search, write, maintenance API |
| `web` | Human UI for upload, browsing, review |
| `mcp` | Agent tool surface |
| `edge` | Internal Nginx entrypoint routing web, API, MCP, and auth |

## The important fix

The original breakage behind messages like **Load failed** and **Unexpected response code** was not about public hosting. It was an internal routing problem caused by browser preflights, forwarded headers, and duplicate or conflicting CORS behavior between layers.

This blueprint keeps the fixes that actually mattered:

- explicit `OPTIONS` responses on auth, API, and MCP routes
- consistent `Access-Control-Allow-*` headers with `always`
- `proxy_hide_header` to avoid duplicate upstream CORS headers
- stable `Host` and `X-Forwarded-*` propagation
- websocket upgrade handling where needed
- internal routing focused on `/`, `/api/`, `/auth/v1/`, and `/mcp`

## Sanitisation note

All environment-specific values are placeholders, for example:

- `KOBE_IP`
- `MAC_MINI_IP`
- `INTERNAL_APP_HOST`
- `YOUR_*`

No real internal IPs, domains, or hostnames should live in this repo.

## Intended use

Use this repo as a blueprint when you want a durable agent memory layer that stays inside a secure perimeter, such as:

- personal research systems
- private family or household knowledge bases
- internal team memory systems
- long-running autonomous agent environments

## Read next

- `setup-guide.md`
- `architecture.md`

### Create the first login user

After the stack is up, create a login-capable first user through GoTrue:

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
DISPLAY_NAME='Admin' \
./scripts/create-initial-user.sh
```

This uses the public auth signup endpoint and then verifies password login. Once your first private user exists, set `GOTRUE_DISABLE_SIGNUP=true` in `.env` and restart with `docker compose up -d` if you do not want open signup.
