# Sovereign Brain

![Validate](https://github.com/LeoStehlik/decoupled-agent-memory/actions/workflows/validate.yml/badge.svg)

Private, source-backed memory for long-running agents.

Sovereign Brain is harness-agnostic. It can serve OpenClaw, Hermes, Codex, OpenCode, Claude Code, or any other agent runtime that can call MCP/API tools or consume source-backed files.

Sovereign Brain turns a pile of notes, logs, decisions, project files, and wiki pages into an operating memory that can answer a harder question than search:

> What is current, what changed, what needs review, and what source evidence supports it?

It is built for the reality of agent work: sessions end, context windows reset, projects keep moving, and yesterday's polished summary can become dangerously stale. The system keeps raw sources as evidence, maintained synthesis as the current view, and a review loop that makes stale knowledge visible instead of quietly trusted.

## What This Repo Is

This repository is the source of truth for the Sovereign Brain / decoupled-agent-memory stack.

It contains:

- a private LLM Wiki-based application under `llmwiki-app/`
- API and MCP overlays for private deployments
- maintenance and freshness checks
- source-backed synthesis review workflows
- a browser Brain console under `/brain`
- demo corpora and proof scripts
- deployment/rebuild scripts for the integrated internal stack
- project history in `CHANGELOG.md`

The project started from Andrej Karpathy's LLM Wiki idea and Lucas Astorian's open-source implementation, then grew into a private agent-memory control plane: authenticated, source-backed, reviewable, and integrated into one product surface.

## The Problem

Most agent memory fails in boring ways:

- raw files get reread instead of understood
- decisions get rediscovered every session
- stale summaries still look authoritative
- contradictions stay hidden
- agents cannot prove where an answer came from
- a "memory system" becomes another archive nobody maintains

Sovereign Brain treats memory as an operational system, not a dumping ground.

## The Model

```text
Raw sources
  -> source documents, logs, briefs, notes, markdown, PDFs

Maintained wiki
  -> pages that compile current understanding

Synthesis pages
  -> opinionated current-state summaries with links back to evidence

Maintenance layer
  -> graph references, duplicate checks, uncited-source checks, stale synthesis checks

Review loop
  -> proposal, evidence map, diff, apply/reject decision, ledger

Agent access
  -> MCP/API tools and source-backed files for OpenClaw, Hermes, Codex, OpenCode, Claude Code, or other harnesses
```

The key rule: synthesis must stay attached to source evidence. When linked sources change, the synthesis becomes review work.

## Harness Compatibility

Sovereign Brain is not tied to one chat product or agent runner. The core boundary is the maintained memory layer: raw evidence, wiki synthesis, review decisions, MCP/API access, and rebuildable deployment artifacts. Any harness that can authenticate to the tools or read the exported files can use the same memory surface.

That means one private brain can support multiple execution layers without turning memory into a vendor-specific prompt cache.

## Current Product Surface

### `/brain`

The Brain console is the main human entry point.

It is integrated into the LLM Wiki product shell and uses the existing login/session. There is no separate token form for normal users.

Tabs:

- **Brief**: trust state, recent changes, and the next useful action
- **Review**: stale synthesis, linked evidence, proposals, and apply/reject controls
- **Health**: raw maintenance counters and graph state
- **Artifacts**: decision ledger and proof trail

### Review Workflow

1. A source changes.
2. Linked synthesis becomes stale.
3. Brain shows the affected page in the review queue.
4. The user generates a source-backed replacement proposal.
5. Brain shows the evidence map, old/new impact, and diff.
6. The user applies or rejects with an optional rationale.
7. The decision is written to the review ledger.

This is the product loop: memory is trusted because it can be checked.

## What Is Included

| Path | Purpose |
| --- | --- |
| `llmwiki-app/` | Vendored LLM Wiki app used as the Sovereign Brain product shell |
| `llmwiki-app/SOVEREIGN_BRAIN.md` | Ownership boundary and deployment notes for the vendored app |
| `overlays/api/` | API overlay: graph routes, maintenance status, hosted auth fixes, proposal/review endpoints |
| `overlays/mcp/` | MCP overlay: private auth compatibility and agent-facing maintenance tools |
| `scripts/rebuild-integrated-llmwiki.sh` | Rebuilds the integrated internal stack from this repo |
| `scripts/sovereign-sync.sh` | Idempotent markdown source/synthesis sync |
| `scripts/brain-brief.sh` | CLI operating brief |
| `scripts/brain-review.sh` | CLI review queue |
| `scripts/propose-review.sh` | Source-backed proposal generation/apply flow |
| `examples/demo-corpus/` | First-run demo corpus |
| `examples/review-demo/` | Stale-source to reviewed-synthesis proof loop |
| `docs/` | Setup, architecture, Brain console, review queue, proposals, and synthesis maintainer docs |
| `CHANGELOG.md` | Retrospective project history and release trail |

## Quick Start

This stack is designed for a private/internal network, not public SaaS exposure.

```bash
cp .env.example .env
# edit .env first

docker compose up -d --build
```

Create the first login user:

```bash
BASE_URL=http://INTERNAL_APP_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
DISPLAY_NAME='Admin' \
./scripts/create-initial-user.sh
```

Run the first demo:

```bash
BASE_URL=http://INTERNAL_APP_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make demo
```

Open:

```text
http://INTERNAL_APP_HOST/brain
```

## Proof Commands

Run the review demo:

```bash
BASE_URL=http://INTERNAL_APP_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make review-demo
```

Run proposal generation and apply proof:

```bash
BASE_URL=http://INTERNAL_APP_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make proposal-demo
```

Run the ledger proof:

```bash
BASE_URL=http://INTERNAL_APP_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make ledger-demo
```

Run the operating brief proof:

```bash
BASE_URL=http://INTERNAL_APP_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
make brief-demo
```

Run smoke checks:

```bash
BASE_URL=http://INTERNAL_APP_HOST \
EMAIL=admin@example.com \
PASSWORD='change-me-long-random-password' \
MCP_TOKEN='replace-with-long-random-mcp-token' \
make smoke
```

## Integrated Internal Rebuild

For the integrated LLM Wiki deployment, this repo owns the source now.

```bash
make rebuild-integrated-llmwiki
```

That script:

- pulls the latest `decoupled-agent-memory`
- builds API and MCP overlay images
- syncs `llmwiki-app/` into the deployment directory
- preserves host-local `.env` and compose configuration
- rebuilds/restarts web, API, and MCP
- checks `/brain`, `/brain-review`, and `/wikis`

## Architecture

| Component | Role |
| --- | --- |
| `db` | Postgres persistence for auth, documents, chunks, references, review decisions, and sync metadata |
| `supabase-auth` | GoTrue auth service |
| `supabase-proxy` | Internal auth proxy and CORS/preflight cleanup |
| `api` | Ingestion, search, write, graph, maintenance, and review APIs |
| `web` | LLM Wiki UI plus the integrated Brain console |
| `mcp` | Agent tool surface for search, read, write, maintenance status, review queue, and briefs |
| `edge` | Internal Nginx entrypoint for web, API, MCP, auth, and static routes |

## Design Principles

- **Evidence first**: answers should trace back to source documents.
- **Current beats complete**: stale synthesis is worse than missing synthesis.
- **Review is a feature**: changed evidence creates visible review work.
- **Agents need tools, not vibes**: expose memory through MCP/API with health checks.
- **Repo is truth**: live tweaks must be committed here or they do not exist.
- **Private by default**: real hosts, tokens, emails, and deployment secrets stay out of git.


## Related Tools

Sovereign Brain is useful on its own, but it sits naturally beside a few small agent-operation tools:

- [Proof Loop](https://github.com/LeoStehlik/proof-loop) - finish coding tasks with frozen ACs, fresh verification, and durable proof artifacts.
- [Loopsmith](https://github.com/LeoStehlik/loopsmith) - turn repeated agent failures into eval packs, candidate comparisons, and promotion decisions.
- [Brief Master](https://github.com/LeoStehlik/brief-master) - write tighter briefs before agent work starts, including explicit success criteria and constraints.

Use Sovereign Brain for memory and source-backed synthesis. Use Proof Loop for task completion discipline. Use Loopsmith when recurring behaviour needs measurable improvement.

## Private Deployment Boundaries

Use placeholders in committed files:

- `INTERNAL_APP_HOST`
- `KOBE_IP`
- `MAC_MINI_IP`
- `YOUR_*`

Keep real IPs, hostnames, domains, tokens, passwords, and email addresses in `.env` or host-local deployment files.

Choose one canonical browser origin. Browsers isolate auth and local storage by origin, so the same server reached through two different hosts can look like two different sessions.

## Attribution

Sovereign Brain builds on the LLM Wiki pattern inspired by Andrej Karpathy and the open-source implementation by Lucas Astorian at `lucasastorian/llmwiki`.

This repository is now the private Sovereign Brain source of truth. Upstream LLM Wiki remains credited as the foundation; Sovereign Brain-specific product, deployment, and agent-memory work lives here.

## Read Next

- `CHANGELOG.md`
- `llmwiki-app/SOVEREIGN_BRAIN.md`
- `docs/setup-guide.md`
- `docs/architecture.md`
- `docs/brain-console.md`
- `docs/review-queue.md`
- `docs/proposals.md`
- `docs/brain-brief.md`
- `docs/synthesis-maintainer.md`
