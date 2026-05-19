-- Sync-run metadata for observable, idempotent ingestion from local files or agents.

CREATE TABLE IF NOT EXISTS sync_runs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    source_count INTEGER NOT NULL DEFAULT 0,
    wiki_page_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_kb_started
    ON sync_runs (knowledge_base_id, started_at DESC);

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS source_ref TEXT,
    ADD COLUMN IF NOT EXISTS source_hash TEXT,
    ADD COLUMN IF NOT EXISTS sync_run_id UUID REFERENCES sync_runs(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS last_synced_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_documents_source_ref
    ON documents (knowledge_base_id, source_ref)
    WHERE source_ref IS NOT NULL AND NOT archived;

CREATE INDEX IF NOT EXISTS idx_documents_last_synced_at
    ON documents (knowledge_base_id, last_synced_at DESC)
    WHERE last_synced_at IS NOT NULL AND NOT archived;

GRANT SELECT, INSERT, UPDATE, DELETE ON sync_runs TO authenticated;
