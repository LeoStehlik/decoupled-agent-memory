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

## API

```text
GET /api/v1/knowledge-bases/{kb_id}/maintenance/review-queue
```

The response includes `review_counts`, `stale_synthesis_pages`, `uncited_sources`, and `duplicate_active_paths`.

## Product Rule

Do not silently refresh synthesis timestamps during source sync. A source-only update should make linked synthesis stale. A reviewed synthesis update should clear the queue.
