-- Document reference graph: citations, cross-references, and stale-page tracking.

CREATE TABLE IF NOT EXISTS document_references (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    source_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    target_document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    reference_type TEXT NOT NULL CHECK (reference_type IN ('cites', 'links_to')),
    page INTEGER,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    UNIQUE(source_document_id, target_document_id, reference_type)
);

CREATE INDEX IF NOT EXISTS idx_document_references_source ON document_references(source_document_id);
CREATE INDEX IF NOT EXISTS idx_document_references_target ON document_references(target_document_id);
CREATE INDEX IF NOT EXISTS idx_document_references_kb ON document_references(knowledge_base_id);

ALTER TABLE documents ADD COLUMN IF NOT EXISTS stale_since TIMESTAMPTZ;

ALTER TABLE document_references ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS document_references_select ON document_references;
CREATE POLICY document_references_select ON document_references
    FOR SELECT TO authenticated
    USING (knowledge_base_id IN (
        SELECT id FROM knowledge_bases WHERE user_id = auth.uid()
    ));

DROP POLICY IF EXISTS document_references_write ON document_references;
CREATE POLICY document_references_write ON document_references
    FOR ALL TO authenticated
    USING (knowledge_base_id IN (
        SELECT id FROM knowledge_bases WHERE user_id = auth.uid()
    ))
    WITH CHECK (knowledge_base_id IN (
        SELECT id FROM knowledge_bases WHERE user_id = auth.uid()
    ));

GRANT SELECT, INSERT, UPDATE, DELETE ON document_references TO authenticated;
