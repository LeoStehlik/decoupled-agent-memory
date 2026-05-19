# Proposal Packages

Proposal packages are the assisted-maintenance layer on top of the review queue.

The review queue says what is stale. Proposal generation gathers the stale synthesis page, linked source evidence, and enough metadata to draft a reviewable update.

## Generate Proposals

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
KB_NAME='Demo Sovereign Brain' \
make propose
```

Output is written to:

```text
out/review-proposals/{knowledge-base-slug}/
```

Each proposal has:

- `*.proposal.md` — the proposed synthesis update.
- `*.proposal.md.json` — metadata: stale page id, linked sources, proposal path, and status.
- `manifest.json` — index of generated proposals.

## Apply Explicitly

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
KB_NAME='Demo Sovereign Brain' \
./scripts/propose-review.sh --apply
```

Apply is intentionally explicit. Source sync should not silently update synthesis, and proposal generation should not silently apply updates.

## Demo

```bash
BASE_URL=http://KOBE_IP \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make proposal-demo
```

The demo imports baseline content, injects newer source evidence, writes proposal packages, applies them, and prints the review queue afterward.
