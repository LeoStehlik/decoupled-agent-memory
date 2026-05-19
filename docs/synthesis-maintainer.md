# Synthesis Maintainer

Sovereign Brain should not stop at source ingestion. The useful layer is maintained synthesis: short pages that state the current operating position and link back to the raw evidence.

## Current live pattern

The live private workspace sync writes three layers into `Private Wiki`:

1. **Source documents**: durable memory files, daily logs, research agent briefs, Product briefs/reports, and selected public writing drafts.
2. **Index pages**: generated category pages under `/wiki/freshness-repair-2026-05-19/` that list synced sources.
3. **Synthesis pages**: maintained pages under `/wiki/synthesis/` that summarize the current state and link to evidence.

The synthesis pages are intentionally opinionated. They should say what matters now, what is done, what is risky, and what should happen next. Every claim should link to source pages so graph rebuilds can expose dependency edges.

## Required synthesis pages

A private deployment should maintain at least:

- `/wiki/synthesis/current-state.md` — top-level operating state.
- `/wiki/synthesis/sovereign-brain-roadmap.md` — product roadmap for the brain itself.
- `/wiki/synthesis/open-questions-and-risks.md` — unresolved risks and contradictions.
- `/wiki/synthesis/product-product-state.md` — Product state and next moves.
- `/wiki/synthesis/client-delivery-state.md` — client delivery and deployment risk posture.
- `/wiki/synthesis/content-distribution-state.md` — public/content distribution posture.

## Maintenance rules

- Prefer conclusions first, source links second.
- Link source pages with normal markdown links, not code spans, so the graph parser records edges.
- Do not bulk-import runtime logs, generated JSON state, or large eval artifacts unless a human explicitly asks for that noise.
- Treat graph edge count as plumbing proof only. It proves pages are connected; it does not prove the synthesis is correct.
- Mark or regenerate synthesis when linked source pages change after the synthesis timestamp.

## Verification gates

After a sync or synthesis update:

1. API health returns ok.
2. The target knowledge base source/page counts move as expected.
3. Duplicate active `(knowledge_base_id, path, filename)` rows remain zero.
4. MCP can read at least one generated synthesis page.
5. Graph rebuild completes and edge count is non-zero.
