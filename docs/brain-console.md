# Sovereign Brain Console

The main human product surface is:

```text
/brain
```

It replaces the "which utility page do I open?" problem with one console:

- **Brief**: trust state, recent changes, current review work, and the next action.
- **Review**: stale synthesis, uncited sources, duplicate paths, and linked evidence.
- **Health**: raw maintenance counters and recent document activity.
- **Artifacts**: proposal, diff, brief, and acceptance-ledger command flow.

The console stores the API origin, bearer token, selected knowledge base, and selected tab in browser `localStorage` when "Remember connection settings" is checked. This is intended for private/internal deployments on trusted machines.

The older pages stay available as deep links:

```text
/brain-brief
/brain-review
/brain-health
```

Use `/brain` as the default product entry point.

## Guided Review Workspace

The Review tab supports the full human review loop from the browser:

1. Select a stale synthesis page.
2. Generate a source-backed proposal.
3. Inspect the proposed synthesis and unified diff side by side.
4. Apply or reject the proposal.
5. Review the resulting decision in the Artifacts ledger.

Browser decisions are stored in the `review_decisions` table with actor, rationale, proposal hash, linked source ids, proposal content, diff content, and timestamp.

The CLI proposal workflow remains available for automation and demos, but the browser is now the default human control surface.
