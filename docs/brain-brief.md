# Brain Brief

The brain brief is the human-facing product surface on top of health checks, review queues, proposal packages, and the acceptance ledger.

It answers:

```text
What changed?
What is stale?
What was repaired?
What should happen next?
```

## CLI

```bash
BASE_URL=http://INTERNAL_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
KB_NAME='Demo Sovereign Brain' \
make brief
```

The script writes:

```text
out/brain-briefs/{knowledge-base-slug}/brain-brief.md
out/brain-briefs/{knowledge-base-slug}/brain-brief.json
```

## Web

Open:

```text
/brain-brief
```

Paste a bearer token, select a knowledge base, and inspect trust status, recent changes, attention items, and the recommended next action.

## MCP

The MCP overlay exposes:

```text
brain_brief
```

Agents should call this before starting work that depends on current memory.

## Demo

```bash
BASE_URL=http://INTERNAL_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make brief-demo
```

The demo creates stale synthesis, prints a brief while review is needed, repairs through the proposal/ledger path, and prints the healthy brief afterward.
