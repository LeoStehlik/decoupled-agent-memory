---
title: Risk Register
tags: [risk, demo, source]
---

# Risk Register

The largest risk is stale synthesis. A page can look polished while depending on source material that changed later. If the system quietly refreshes timestamps without a real review, users get confidence theatre instead of memory.

## Current Risks

- Synthesis pages can lag behind raw notes.
- Imported files can duplicate if sync is not idempotent.
- Browser sessions can split when the same service is reached through multiple origins.
- Agent-written pages can become invisible if static-token auth maps to a hidden service user.

## Required Control

The maintenance layer must report stale synthesis and duplicate active paths before the system claims to be healthy.
