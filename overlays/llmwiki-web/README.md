# LLM Wiki Integrated Brain Overlay

This overlay preserves the live LLM Wiki integration work that turns Sovereign Brain
from a standalone console into an authenticated LLM Wiki product surface.

The upstream checkout tracks the base LLM Wiki project.
Sovereign Brain-specific changes should not be pushed directly there as durable
product work. Keep these files in this repo as the source of truth for the integrated
Brain layer until the work is promoted into a proper fork or upstream-compatible PR.

## Included Surface

- `web/src/app/(dashboard)/brain/page.tsx`
  - authenticated `/brain` dashboard inside the LLM Wiki shell
  - Brief, Review, Health, and Artifacts tabs
  - Next attention ranking
  - source-backed proposal view
  - proof-loop state strip
  - post-apply navigation back to the updated synthesis page
- `web/src/app/(dashboard)/brain-review/page.tsx`
- `web/src/app/(dashboard)/brain-health/page.tsx`
- `web/src/app/(dashboard)/brain-brief/page.tsx`
  - compatibility routes that redirect to `/brain?view=...`
- `web/src/app/(dashboard)/wikis/page.tsx`
  - adds the Brain entrypoint to the LLM Wiki header
- `web/src/app/(auth)/login/LoginForm.tsx`
  - removes the dead Google auth button for the local GoTrue deployment
- `web/Dockerfile`
  - bakes public Supabase/API env vars into the Next browser bundle at build time
- `web/src/proxy.ts`
  - canonical-host redirect support for the deployed internal origin

## Deployment Note

In the captured deployment, these files are applied to an upstream LLM Wiki checkout and the web container is rebuilt.

Verification for the captured version:

- Docker/Next production build passed compile and TypeScript.
- `/brain`, `/brain-review`, and `/wikis` returned `200 text/html` on the deployed `:3030` LLM Wiki origin.
- Live Brain API checks returned `200` for `maintenance/status`,
  `maintenance/review-queue`, and `maintenance/review-decisions`.
