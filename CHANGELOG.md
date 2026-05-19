# Changelog

All notable changes to the Sovereign Brain / decoupled-agent-memory project are recorded here. The repository is the source of truth for the running system.

## 2026-05-20

### Added
- Vendored the relevant LLM Wiki application into `llmwiki-app/` so Sovereign Brain work no longer depends on Lucas Astorian's upstream repository.
- Added `llmwiki-app/SOVEREIGN_BRAIN.md` to document the ownership boundary, deployment intent, and why this app copy exists inside decoupled-agent-memory.
- Added an integrated rebuild script, `scripts/rebuild-integrated-llmwiki.sh`, that builds API/MCP overlays, syncs the vendored LLM Wiki app, preserves host-local runtime configuration, restarts the integrated stack, and verifies key routes.
- Added retrying route checks for `/brain`, `/brain-review`, and `/wikis` as part of the rebuild flow.
- Added evidence-map metadata to review proposals and persisted it in review-decision metadata.

### Changed
- Switched the live integrated LLM Wiki deployment to be rebuilt from the decoupled-agent-memory repository instead of a separate upstream checkout.
- Improved review proposal generation so candidates are replacement-oriented, remove stale generated review blocks, preserve frontmatter, and include concise source-backed evidence.
- Updated the Brain review UI to label generated updates as replacement synthesis, show evidence basis/source excerpts, explain old-vs-new application impact, and require explicit confirmation before applying replacements.
- Hardened the rebuild path after proof testing exposed a missing Supabase nginx file in the vendored app tree.

### Verified
- Rebuilt and redeployed the integrated LLM Wiki stack from repository-owned source.
- Confirmed `/brain`, `/brain-review`, and `/wikis` returned HTTP 200 after rebuild.
- Confirmed authenticated Brain maintenance API endpoints returned HTTP 200.
- Confirmed the browser bundle contained the updated review action text.
- Committed and pushed the proposal-quality slice as `518a14d Improve Brain proposal review quality`.

## 2026-05-19

### Added
- Added hosted API graph and sync hardening for the Sovereign Brain data path.
- Added source-link resolution during graph rebuilds so graph nodes can point back to their source material.
- Added synthesis-maintainer documentation and separated source-sync freshness from synthesis freshness.
- Added knowledge-base maintenance status APIs and the matching MCP maintenance status tool.
- Added a productized Sovereign Brain demo loop for showing current health, freshness, and value instead of a static login/demo shell.
- Added a review queue for stale or questionable synthesis pages.
- Added review proposal generation for synthesis updates.
- Added a proposal acceptance ledger backed by the `review_decisions` table.
- Added an operating brief view for the Sovereign Brain console.
- Added a unified `/brain` console and a guided review workspace.
- Added integrated LLM Wiki routes so legacy `/brain-review`, `/brain-health`, and `/brain-brief` entry points resolve into the unified Brain surface.
- Added an authenticated Brain dashboard under the LLM Wiki product shell using the existing login/session flow.
- Added a Brain link from the LLM Wiki navigation and a clean path back from Brain into LLM Wiki.
- Added a proof-loop strip and source/evidence panels to make the Brain workflow easier to trust.

### Changed
- Repaired the freshness path for Private Wiki so current workspace, daily, research agent, Product, and public-writing sources could be synced back into the live knowledge base.
- Made source sync idempotent and focused on freshness rather than raw document count.
- Moved Brain pages away from a bolt-on standalone UI into the LLM Wiki product skin: same header rhythm, back button pattern, user menu behavior, warm background/card tokens, compact tabs, and neutral status styling.
- Reworked Brain from a single opaque dashboard into a reviewable workflow: operator brief, next-attention ranking, review queue, health, artifacts, source drilldown, proposal basis, and apply controls.
- Fixed `/brain` exposure on the public `:3030` LLM Wiki surface instead of leaving it bound to an internal-only route.
- Fixed the web Docker build so public Supabase browser environment variables are baked into the Next.js bundle.
- Removed the dead Google login affordance from the login page.
- Restored canonical proxy/redirect handling for the integrated web surface.

### Fixed
- Fixed `/brain` 404 and route-boundary failures on the live integrated deployment.
- Fixed a missing `review_decisions` database table used by the review ledger.
- Fixed login crashes caused by missing `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` at web build time.
- Fixed stale-synthesis checks that previously confused source freshness with synthesis freshness.
- Fixed inconsistent visual language between LLM Wiki and the first Brain pages.

### Verified
- Verified live LLM Wiki routes returned HTTP 200 on the `:3030` surface.
- Verified Brain maintenance endpoints returned HTTP 200, including review decisions.
- Verified the active knowledge base had no duplicate active paths and no stale synthesis pages after the freshness repair.
- Verified Next.js build/typecheck passed during the integrated UI slices.

### Key Commits
- `4eeae4e Add hosted API graph and sync hardening`
- `c61ad67 Resolve source links in graph rebuild`
- `c59f4ac Document synthesis maintainer layer`
- `1b1f06b Add knowledge base maintenance status API`
- `fbac516 Add MCP maintenance status tool`
- `622af48 Separate source sync from synthesis freshness`
- `c793c58 Productize Sovereign Brain demo loop`
- `d1bac86 Add Sovereign Brain review queue`
- `30bd6af Add review proposal generator`
- `db46c9f Add proposal acceptance ledger`
- `50d349b Add Sovereign Brain operating brief`
- `8ce16b2 Add unified Sovereign Brain console`
- `0948d59 Add guided review workspace`
- `6375b03 Route legacy brain pages to integrated UI`
- `9a74396 Capture integrated LLM Wiki Brain overlay`
- `f9a62ef Align review decisions migration with live deployment`
- `e2b2002 Add integrated LLM Wiki rebuild script`
- `c7ff703 Vendor LLM Wiki app for Sovereign Brain`

## 2026-05-13

### Added
- Added public-stack bootstrap documentation and initial-user onboarding notes.
- Added canonical-origin documentation for the public web stack.
- Added MCP bearer-authentication documentation and an MCP auth overlay.
- Added visible-user ownership documentation for MCP interactions.

### Changed
- Made the public stack reproducible from source and container configuration instead of relying on one-off live fixes.
- Patched web URL handling so baked runtime URLs can be corrected at container startup.
- Switched the portable web image path to use the rebuilt image directly.

### Fixed
- Fixed public stack authentication and frontend runtime configuration.
- Fixed auth database creation during bootstrap.
- Marked the initial user as onboarded so the clean public stack could pass real login smoke testing.
- Removed generated Python cache files from the repository.

### Verified
- Verified clean public-stack login in a real browser.
- Verified GHCR image/public runtime fixes before documenting the stack as reproducible.

### Key Commits
- `0648eef Create auth database during bootstrap`
- `3a488c9 Fix public stack auth and frontend config`
- `ba8ff05 Patch baked web URLs at startup`
- `0261563 Document initial user bootstrap`
- `d758bf3 Use rebuilt portable web image directly`
- `585e5bb Mark initial user onboarded`
- `bdc0b2a Document canonical origin handling`
- `4282916 Document MCP bearer authentication`
- `3557cb4 Add MCP auth overlay`
- `650375a Remove generated Python cache files`
- `f853c14 Document visible user ownership for MCP`

## Initial Project

### Added
- Created the initial decoupled-agent-memory blueprint.
- Added an MIT license.
- Added Postgres initialization migrations for the project runtime.

### Key Commits
- `8611894 Initial release of the decoupled-agent-memory blueprint`
- `d4665f9 Add MIT License`
- `6f60d3d Add Postgres init migrations`
