# Sovereign Brain

A private memory layer for long-running agents: source-backed wiki pages, maintained synthesis, graph references, and freshness checks that make stale knowledge visible.

## Why It Matters

Most agent systems lose time and trust because every session reconstructs context from raw files. Notes get reread, decisions get rediscovered, contradictions stay buried, and polished summaries keep looking current after the source material has changed.

Sovereign Brain turns that into a maintained operating memory:

1. **Raw sources** remain the evidence layer.
2. **Wiki pages** compile the current understanding.
3. **Synthesis pages** state what matters now and link back to sources.
4. **Maintenance checks** report stale synthesis, duplicate active paths, uncited sources, and graph health.
5. **MCP/API access** lets agents read, write, and verify memory instead of improvising it.

The product promise is simple: an agent should be able to ask one private workspace what changed, what is current, what is risky, and which source documents support the answer.

## Fast Demo

Start the stack, create a first user, import the sample corpus, rebuild references, and run maintenance:

```bash
cp .env.example .env
# edit .env placeholders first

docker compose up -d --build

BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make demo
```

The demo imports `examples/demo-corpus`, creates maintained synthesis pages, rebuilds the graph, and prints the wiki and health URLs.

Open the health page:

```text
http://KOBE_IP/brain-health
```

Paste a Supabase user token or trusted static bearer token to inspect one knowledge base. For a password-login demo user, get a token with `BASE_URL=http://KOBE_IP EMAIL=admin@example.com PASSWORD=change-me-long-random-password ./scripts/get-token.sh`.

Run the review demo:

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make review-demo
```

The review demo imports the baseline corpus, updates one source document so linked synthesis becomes stale, prints the review queue, then applies a reviewed synthesis update and proves the queue clears. Open the operator page at:

```text
http://KOBE_IP/brain-review
```

## What Is Included

- `docker-compose.yml` for the internal stack.
- `overlays/api/` for private hosted API fixes, graph routes, maintenance status, and idempotent document identity support.
- `overlays/mcp/` for static bearer auth, HS256 Supabase JWT compatibility, host+port MCP DNS-rebinding allowance, and maintenance tools.
- `static/brain-health.html` for a lightweight human health surface.
- `static/brain-review.html` for the human synthesis review queue.
- `examples/demo-corpus/` for a realistic first-run demo.
- `examples/review-demo/` for a stale-source to reviewed-synthesis proof loop.
- `scripts/bootstrap-demo.sh` for first-run demo setup.
- `scripts/sovereign-sync.sh` for idempotent markdown sync.
- `scripts/brain-review.sh` for terminal review briefings.
- `scripts/review-demo.sh` for the end-to-end freshness review demo.
- `scripts/smoke-test.sh` for login/API/MCP/maintenance proof.
- `docs/synthesis-maintainer.md` for the maintained synthesis pattern.

## Core Components

| Component | Role |
| --- | --- |
| `db` | Postgres persistence for documents, wiki pages, auth data, references, and sync metadata |
| `supabase-auth` | GoTrue auth service |
| `supabase-proxy` | Internal auth proxy with preflight handling and header cleanup |
| `api` | Ingestion, search, write, graph, and maintenance API |
| `web` | Human UI for upload, browsing, and review |
| `mcp` | Agent tool surface for search, read, write, and maintenance checks |
| `edge` | Internal Nginx entrypoint routing web, API, MCP, auth, and health page |

## Product Surfaces

### Maintained Synthesis

Synthesis pages live under `/wiki/synthesis/`. They should be short, opinionated, and source-backed. They are not generated filler; they are the current operating position with links to evidence.

### Brain Health

`/brain-health` reports:

- active documents
- source documents
- wiki pages
- synthesis pages
- reference edges
- duplicate active paths
- stale synthesis pages
- uncited sources
- recent changes

This is the trust surface. Do not claim a brain is healthy until this is clean.

### Brain Review

`/brain-review` shows the operator queue behind the health warning:

- stale synthesis pages
- newer linked sources that caused staleness
- uncited source candidates
- duplicate active paths

This is the product loop: changed source evidence creates review work, reviewed synthesis clears the queue, and health returns to clean.

### Sync CLI

`./scripts/sovereign-sync.sh` logs in, creates or finds a knowledge base, upserts markdown source files, upserts synthesis files, optionally rebuilds the graph, and prints maintenance status.

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
KB_NAME='Demo Sovereign Brain' \
./scripts/sovereign-sync.sh
```

### Smoke Test

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
MCP_TOKEN='replace-with-long-random-mcp-token' \
make smoke
```

## Attribution

This repository is an internal/private deployment blueprint derived from **Andrej Karpathy's LLM Wiki** pattern and the open-source implementation by **Lucas Astorian** at `lucasastorian/llmwiki` (`https://github.com/lucasastorian/llmwiki`). Keep that credit prominent in downstream reuse.

## Private Deployment Boundaries

This is not a public SaaS template. It is built for a trusted network perimeter, for example a private server plus internal clients. Real IPs, domains, tokens, emails, and hostnames belong in `.env`, not in the repo.

Use placeholders such as:

- `KOBE_IP`
- `MAC_MINI_IP`
- `INTERNAL_APP_HOST`
- `YOUR_*`

## Read Next

- `docs/product-demo.md`
- `docs/setup-guide.md`
- `docs/review-queue.md`
- `docs/synthesis-maintainer.md`
- `docs/architecture.md`
