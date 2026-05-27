# Setup Guide

This guide explains how to deploy Sovereign Brain as an **internal-only** service, with a trusted client talking to an internal server across a trusted network.

## Deployment shape

```text
Internal client
  -> http://INTERNAL_HOST:80
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
- an internal server, referenced here as `INTERNAL_HOST`
- internal clients that can reach `http://INTERNAL_HOST`
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
- `LOCAL_USER_ID` and `STATIC_BEARER_TOKEN` if a trusted local agent will connect over MCP without an interactive Supabase user token
- `APP_URL`
- `SUPABASE_URL`
- `NEXT_PUBLIC_*`
- `API_BASE_IMAGE` and `API_IMAGE`
- `WEB_IMAGE`
- `MCP_IMAGE`

Recommended internal values:

- `APP_URL=http://INTERNAL_HOST`
- `APP_URLS=http://INTERNAL_HOST,http://CLIENT_IP`
- `SUPABASE_URL=http://INTERNAL_HOST`
- `SUPABASE_AUTH_EXTERNAL_URL=http://INTERNAL_HOST/auth/v1`
- `NEXT_PUBLIC_API_URL=http://INTERNAL_HOST/api`
- `NEXT_PUBLIC_SUPABASE_URL=http://INTERNAL_HOST`
- `NEXT_PUBLIC_MCP_URL=http://INTERNAL_HOST/mcp`
- `NEXT_PUBLIC_CANONICAL_HOST=INTERNAL_HOST` or your stable internal hostname
- `NEXT_PUBLIC_CANONICAL_REDIRECT_HOSTS=ALTERNATE_INTERNAL_HOST,OLD_HOSTNAME` for any alternate addresses that should redirect to the canonical browser origin

Important: `SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_URL` must be the public base origin, for example `http://INTERNAL_HOST`. Do not include `/auth/v1`; the clients append that path themselves. `SUPABASE_AUTH_EXTERNAL_URL` is the GoTrue external auth URL and should include `/auth/v1`.

Choose one canonical browser origin and stick to it. Browsers isolate auth cookies and local storage by origin, so reaching the same stack as `http://INTERNAL_HOST` in one tab and `http://ALTERNATE_INTERNAL_HOST` in another can look like two different sessions or users. Set `NEXT_PUBLIC_CANONICAL_HOST` to the preferred host and list any old/internal aliases in `NEXT_PUBLIC_CANONICAL_REDIRECT_HOSTS`.

For MCP clients, configure the client with the MCP URL and a bearer header. Example MCP client shape:

```json
{
  "mcpServers": {
    "llmwiki": {
      "url": "http://INTERNAL_HOST/mcp",
      "headers": {
        "Authorization": "Bearer replace-with-long-random-mcp-token"
      }
    }
  }
}
```

The static token is only for trusted private-network agent clients. Browser users should still authenticate through GoTrue/Supabase.

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
docker compose build api mcp
docker compose up -d
```

`API_BASE_IMAGE` must point at an API image compatible with the current upstream `llmwiki` API modules. If a published base image lags behind upstream, build or pull the current upstream API image first and use it as `API_BASE_IMAGE`; the Sovereign Brain overlay then adds hosted auth, graph, websocket, and private-deployment behavior on top.

## 5. Validate health from a client on the internal network

```bash
docker compose ps
docker compose logs -f edge api web mcp supabase-proxy supabase-auth
```

Then test from a trusted client:

```bash
curl -I http://INTERNAL_HOST/
curl -I http://INTERNAL_HOST/api/health
curl -I http://INTERNAL_HOST/auth/v1/health
# If you configured alternate redirect hosts, this should return 308 to the canonical origin:
curl -I http://ALTERNATE_INTERNAL_HOST/
curl -i -X OPTIONS http://INTERNAL_HOST/auth/v1/token \
  -H Origin: http://CLIENT_IP \
  -H Access-Control-Request-Method: POST
```

That `OPTIONS` request is the fast sanity check for the original browser failure.

## 6. What fixed the browser errors

The working configuration depends on a few specifics:

- `OPTIONS` requests return `204` before they hit app logic
- auth responses do not emit duplicate `Access-Control-Allow-Origin` headers
- upstream auth headers are forwarded cleanly
- `X-Forwarded-Proto`, `X-Forwarded-Host`, and `Host` remain coherent
- non-canonical browser origins redirect before the app/auth layer can create a second session
- websocket upgrade headers are preserved where required

If the UI shows `Load failed` or `Unexpected response code`, check these proxy rules first.


### Create the first login user

After the stack is up, create a login-capable first user through GoTrue:

```bash
BASE_URL=http://INTERNAL_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
DISPLAY_NAME='Admin' \
./scripts/create-initial-user.sh
```

This uses the public auth signup endpoint, verifies password login, and marks the user onboarded through the API. Set `COMPLETE_ONBOARDING=false` if you only want to create the login. Once your first private user exists, set `GOTRUE_DISABLE_SIGNUP=true` in `.env` and restart with `docker compose up -d` if you do not want open signup.

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
- do not treat multiple raw IPs as equally valid browser entrypoints; pick one canonical origin and redirect the rest
- do not skip the auth preflight test
- do not point agents only at raw files and call that memory
