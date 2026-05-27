# Sync CLI

`./scripts/sovereign-sync.sh` is an opinionated markdown sync helper for demos and private deployments.

It:

1. logs in through Supabase password auth,
2. creates or reuses a knowledge base,
3. upserts source markdown files,
4. upserts synthesis markdown files,
5. rebuilds graph references when possible,
6. prints maintenance status.

## Example

```bash
BASE_URL=http://INTERNAL_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
KB_NAME='Demo Sovereign Brain' \
SOURCE_DIR=examples/demo-corpus/sources \
SYNTHESIS_DIR=examples/demo-corpus/synthesis \
./scripts/sovereign-sync.sh
```

## Smoke Test

`./scripts/smoke-test.sh` verifies login, `/v1/me`, knowledge-base listing, maintenance status, and optional MCP initialization.

```bash
BASE_URL=http://INTERNAL_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
MCP_TOKEN='replace-with-long-random-mcp-token' \
./scripts/smoke-test.sh
```
