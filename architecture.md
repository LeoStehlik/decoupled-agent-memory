# Architecture

## Goal

Turn raw source material into a maintained, queryable, agent-usable knowledge layer that runs inside a private network perimeter.

## System overview

```text
Raw Files -> Ingestion/API -> Postgres -> Synthesis workflows -> Wiki Pages -> MCP/API -> Humans and Agents
```

## Deployment shape

```text
internal client / remote client
  -> Internal edge Nginx on internal host
    -> Web
    -> API
    -> MCP
    -> Supabase Auth Proxy
         -> GoTrue Auth
    -> Postgres
```

## Data flow from raw files to synthesis

### 1. Raw acquisition

Inputs can include:

- PDFs
- markdown notes
- meeting transcripts
- exported docs
- HTML captures
- screenshots or OCR output

These remain the immutable evidence layer.

### 2. Ingestion

The API accepts uploads, stores metadata, chunks content, and records provenance.

Responsibilities here:

- file registration
- metadata extraction
- OCR or format conversion when needed
- chunk indexing
- source ownership and access control

### 3. Storage

Postgres stores:

- documents
- chunks
- wiki pages
- user and auth state
- knowledge-base boundaries
- maintenance metadata
- document references and stale-page markers for graph-aware wiki upkeep
- sync-run/source identity metadata for idempotent agent ingestion

This is the durable substrate.

### 4. Synthesis loop

An agent or scheduled workflow reads new source material and updates the compiled layer:

- source summary pages
- entity pages
- concept pages
- timelines
- open questions
- contradiction reports
- link graphs between related pages

The important shift is that knowledge is maintained, not recreated from scratch for each query.

### 5. Access layer

The MCP service exposes tools such as:

- search
- read
- write
- delete or archive
- maintenance workflows

That gives agents a structured interface to the knowledge layer without shell-level access.

### 6. Human interface

The web app lets humans:

- upload source material
- inspect source provenance
- read compiled pages
- review contradictions
- guide what should be synthesised next

## Why the proxy layer matters

There are two proxy layers in this blueprint.

### Edge proxy

Routes internal client traffic to the correct service:

- `/` -> web
- `/api/` -> api
- `/mcp` -> mcp
- `/auth/v1/` -> auth proxy

### Supabase auth proxy

Normalises browser interaction with auth endpoints and fixes the failure class caused by missing preflight handling, inconsistent forwarded headers, and duplicate upstream CORS headers.

Without that layer, browsers can fail before your application logic even runs.

## Design principles

- raw evidence stays immutable
- synthesis is additive, traceable, and maintained as first-class wiki pages
- agents should update knowledge as they work
- auth and CORS behavior must be explicit
- internal templates should stay sanitised and portable
- private deployments should document real routing logic, not fake internet assumptions
