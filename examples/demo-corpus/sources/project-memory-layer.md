---
title: Project Memory Layer
tags: [project, memory, demo]
---

# Project Memory Layer

The product should act as a private memory layer for long-running agents. It should accept raw sources, maintain compiled pages, expose a graph of references, and tell the user when synthesis pages are stale.

## Product Promise

An agent should be able to ask one maintained workspace what changed, what is current, what is risky, and which source documents support the answer.

## Acceptance Criteria

- Raw source documents are preserved.
- Wiki pages link back to source documents.
- Maintenance status reports duplicate paths, stale synthesis, uncited sources, and graph edge count.
- A human can inspect the current state without reading every raw note.
