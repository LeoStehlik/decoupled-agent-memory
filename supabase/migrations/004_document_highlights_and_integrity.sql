-- Highlights plus document identity guardrails for idempotent sync and MCP writes.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS highlights JSONB NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_documents_source_url
    ON documents (user_id, (metadata->>'source_url'))
    WHERE metadata ? 'source_url' AND NOT archived;

-- One live document per path+filename per knowledge base. Historical copies should
-- be archived or versioned, not duplicated as active rows.
CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_unique_active
    ON documents (knowledge_base_id, path, filename)
    WHERE NOT archived;
