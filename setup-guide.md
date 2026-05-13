# Setup Guide

This guide explains how to deploy Sovereign Brain as an **internal-only** service, with a remote client or internal client talking to internal host across a trusted network.

## Deployment shape

```text
internal client / remote client
  -> http://KOBE_IP:80
      -> internal edge nginx
          -> web
          -> api
          -> mcp
          -> supabase-proxy
              -> supabase-auth
          -> db
```

The important point is that everything stays on the private side. There is no public DNS, no TLS termination requirement in this blueprint, and no assumption that anything is internet-facing.

## 1. Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- an internal server, referenced here as `KOBE_IP`
- internal clients that can reach `http://KOBE_IP`
- container images for API, Web, and MCP published somewhere the server can pull from

## 2. Prepare the host

```bash
mkdir -p /opt/sovereign-brain
cd /opt/sovereign-brain
cp .env.example .env
```

Edit `.env` and replace every placeholder.

At minimum set:

- `POSTGRES_PASSWORD`
- `SUPABASE_JWT_SECRET`
- `SUPABASE_ANON_KEY`
- `APP_URL`
- `SUPABASE_URL`
- `NEXT_PUBLIC_*`
- `API_IMAGE`
- `WEB_IMAGE`
- `MCP_IMAGE`

Recommended internal values:

- `APP_URL=http://KOBE_IP`
- `APP_URLS=http://KOBE_IP,http://MAC_MINI_IP`
- `SUPABASE_URL=http://KOBE_IP`
- `SUPABASE_AUTH_EXTERNAL_URL=http://KOBE_IP/auth/v1`
- `NEXT_PUBLIC_API_URL=http://KOBE_IP/api`
- `NEXT_PUBLIC_SUPABASE_URL=http://KOBE_IP`
- `NEXT_PUBLIC_MCP_URL=http://KOBE_IP/mcp`

Important: `SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_URL` must be the public base origin, for example `http://KOBE_IP`. Do not include `/auth/v1`; the clients append that path themselves. `SUPABASE_AUTH_EXTERNAL_URL` is the GoTrue external auth URL and should include `/auth/v1`.

## 3. Review the two Nginx layers

Files to review:

- `infra/nginx/conf.d/llm-wiki.conf`
- `infra/supabase/nginx.conf`

These are the key files behind the fix.

The edge config handles internal routing for `/`, `/api/`, `/mcp`, and `/auth/v1/`.
The Supabase proxy config handles auth preflights and prevents duplicate or conflicting CORS headers from leaking through.

## 4. Start the stack

```bash
docker compose pull
docker compose up -d
```

## 5. Validate health from a client on the internal network

```bash
docker compose ps
docker compose logs -f edge api web mcp supabase-proxy supabase-auth
```

Then test from the internal client or another trusted client:

```bash
curl -I http://KOBE_IP/
curl -I http://KOBE_IP/api/health
curl -I http://KOBE_IP/auth/v1/health
curl -i -X OPTIONS http://KOBE_IP/auth/v1/token \
  -H Origin: http://MAC_MINI_IP \
  -H Access-Control-Request-Method: POST
```

That `OPTIONS` request is the fast sanity check for the original browser failure.

## 6. What fixed the browser errors

The working configuration depends on a few specifics:

- `OPTIONS` requests return `204` before they hit app logic
- auth responses do not emit duplicate `Access-Control-Allow-Origin` headers
- upstream auth headers are forwarded cleanly
- `X-Forwarded-Proto`, `X-Forwarded-Host`, and `Host` remain coherent
- websocket upgrade headers are preserved where required

If the UI shows `Load failed` or `Unexpected response code`, check these proxy rules first.


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

## 7. Hardening for a private deployment

- bind exposure to the private interface only if possible
- restrict which internal clients may reach port 80
- keep signups disabled unless you actually need them
- move secrets into a real secret store if this grows beyond a lab setup
- back up Postgres volumes on a schedule
- pin image tags instead of relying on `latest`

## 8. Migration strategy for existing memory

1. collect raw notes, PDFs, transcripts, exports, and markdown
2. ingest them through the API or your ingestion pipeline
3. run an initial synthesis pass to create wiki pages and entity pages
4. point your agent runtime at the MCP endpoint
5. make wiki maintenance part of normal agent work

## 9. What not to do

- do not reintroduce public DNS or TLS assumptions into this repo
- do not mix real internal IPs or hostnames into committed files
- do not skip the auth preflight test
- do not point agents only at raw files and call that memory
