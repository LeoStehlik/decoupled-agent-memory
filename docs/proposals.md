# Proposal Packages

Proposal packages are the assisted-maintenance layer on top of the review queue.

The review queue says what is stale. Proposal generation gathers the stale synthesis page, linked source evidence, and enough metadata to draft a reviewable update.

## Generate Proposals

```bash
BASE_URL=http://INTERNAL_HOST \
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
- `*.proposal.md.diff.md` — unified diff from original synthesis to proposed synthesis.
- `*.proposal.md.json` — metadata: stale page id, linked sources, proposal path, and status.
- `manifest.json` — index of generated proposals.
- `review-decisions.jsonl` — append-only proposed/applied/rejected decision ledger.

## Apply Explicitly

```bash
BASE_URL=http://INTERNAL_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
KB_NAME='Demo Sovereign Brain' \
./scripts/propose-review.sh --apply
```

Apply is intentionally explicit. Source sync should not silently update synthesis, and proposal generation should not silently apply updates.

## Acceptance Ledger

Every proposal generation and explicit apply appends one JSONL entry with:

- timestamp
- knowledge base id/name/slug
- synthesis document id/path
- proposal path
- diff path
- proposal SHA-256
- linked source ids
- action: `proposed` or `applied`
- actor
- rationale

Use `--actor` and `--rationale` to make the ledger meaningful:

```bash
./scripts/propose-review.sh --actor francis --rationale "Reviewed newer risk-register evidence."
./scripts/propose-review.sh --apply --actor francis --rationale "Accepted generated proposal after source-backed review."
```

## Demo

```bash
BASE_URL=http://INTERNAL_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make proposal-demo
```

The demo imports baseline content, injects newer source evidence, writes proposal packages, applies them, and prints the review queue afterward.

For the full audit proof, run:

```bash
make ledger-demo
```
