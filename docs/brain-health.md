# Brain Health Page

The health page is served at:

```text
/brain-health
```

It is a static internal page that calls the hosted API with a bearer token. It avoids adding a full web-app fork while still giving humans a direct product surface.

## Counters

- **Active documents**: all non-archived documents in the knowledge base.
- **Source documents**: non-wiki evidence documents.
- **Wiki pages**: compiled pages under `/wiki/`.
- **Synthesis pages**: maintained pages under `/wiki/synthesis/`.
- **Reference edges**: links/citations produced by graph rebuild.
- **Duplicate paths**: active `(knowledge_base_id, path, filename)` collisions. This should be zero.
- **Stale synthesis**: synthesis pages older than linked source documents. This should be zero after review.
- **Uncited sources**: recent source documents not referenced by any wiki page.

## Rule

If stale synthesis or duplicate active paths are non-zero, the brain needs review before anyone claims it is healthy.

## Getting A Token

For a password-login demo user:

```bash
BASE_URL=http://INTERNAL_HOST \
EMAIL=admin@example.com \
PASSWORD=change-me-long-random-password \
./scripts/get-token.sh
```

For trusted local agents, paste the configured `STATIC_BEARER_TOKEN`.

## Review Queue

When health reports stale synthesis, open:

```text
/brain-review
```

The review page uses `GET /v1/knowledge-bases/{kb_id}/maintenance/review-queue` to show the synthesis pages that need review, the linked source evidence, uncited sources, and duplicate paths.

For the higher-level operating view, open `/brain-brief` or run `make brief`.
