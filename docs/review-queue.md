# Review Queue

The review queue is the action layer behind Brain Health. Health can say synthesis is stale; the review queue shows what to review and which source evidence caused it.

## Run The Demo

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make review-demo
```

The demo does four things:

1. Imports the baseline demo corpus.
2. Updates a linked source document without touching synthesis.
3. Prints the review queue.
4. Applies a reviewed synthesis update and prints maintenance status again.

Open the human surface:

```text
http://KOBE_IP/brain-review
```

## CLI

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
KB_NAME='Demo Sovereign Brain' \
make review
```

The CLI prints:

- stale synthesis pages
- linked sources and excerpts
- uncited source candidates
- duplicate active paths

## Proposal Packages

Once the queue shows stale synthesis, generate source-backed proposal files:

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
KB_NAME='Demo Sovereign Brain' \
make propose
```

See `proposals.md` for the proposal/apply loop.

Use `make ledger-demo` to prove the generated diff and append-only decision ledger.

## API

```text
GET /api/v1/knowledge-bases/{kb_id}/maintenance/review-queue
```

The response includes `review_counts`, `stale_synthesis_pages`, `uncited_sources`, and `duplicate_active_paths`.

## Product Rule

Do not silently refresh synthesis timestamps during source sync. A source-only update should make linked synthesis stale. A reviewed synthesis update should clear the queue.

## Ignored Uncited Sources

Some imported sources are intentionally kept searchable without becoming review debt when they are not cited by synthesis pages. The uncited-source queue ignores:

- daily `llmwiki-maintenance-YYYY-MM-DD.md` reports
- OpenClaw bootstrap/config files in the workspace root (`AGENTS.md`, `HEARTBEAT.md`, `IDENTITY.md`, `MEMORY.md`, `SOUL.md`, `TOOLS.md`, `USER.md`)
- files under `/memory/`
- accepted working evidence from operators product discussions, briefs, audits, and idea-building sessions

These documents can still be cited by synthesis pages when useful; they just do not create an uncited-source attention item by default.
