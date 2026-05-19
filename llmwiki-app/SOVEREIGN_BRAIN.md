# LLM Wiki App Snapshot

This directory is the Sovereign Brain-owned LLM Wiki application snapshot.
It exists because Sovereign Brain / decoupled-agent-memory must not depend on
Lucas Astorian's upstream checkout for live deployment or product work.

The code here includes the integrated Brain UI and the LLM Wiki app source needed
for the internal host deployment path. Runtime secrets, host-specific `.env` files,
node modules, build outputs, backup files, and the old upstream `.git` metadata
are intentionally excluded.

## Source Of Truth

For Sovereign Brain work, this repository is the source of truth:

- `llmwiki-app/` - full app source used for rebuilds
- `overlays/api/` - Sovereign Brain API overlay
- `overlays/mcp/` - Sovereign Brain MCP overlay
- `supabase/migrations/` - database schema used by Sovereign Brain
- `scripts/rebuild-integrated-llmwiki.sh` - internal host rebuild path

The old `/opt/sovereign-brain/repos/llmwiki` checkout is no longer a durable source of truth.
At most, it can be treated as a historical/deployment scratch checkout.

## Rebuild

On internal host:

```bash
cd /opt/sovereign-brain/sovereign-brain-repo
make rebuild-integrated-llmwiki
```

The script copies this app snapshot into the deployment directory, preserves
host-specific `.env`/compose files, rebuilds the containers, restarts them, and
checks the key integrated routes.
