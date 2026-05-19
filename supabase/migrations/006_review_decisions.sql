-- Browser-native review decisions for stale synthesis proposals.

CREATE TABLE IF NOT EXISTS review_decisions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    synthesis_document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    action TEXT NOT NULL CHECK (action IN ('proposed', 'applied', 'rejected')),
    actor TEXT NOT NULL DEFAULT 'operator',
    rationale TEXT,
    proposal_content TEXT,
    diff_content TEXT,
    proposal_sha256 TEXT,
    linked_source_ids UUID[] NOT NULL DEFAULT '{}'::uuid[],
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_decisions_kb_created
    ON review_decisions (knowledge_base_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_decisions_synthesis
    ON review_decisions (synthesis_document_id, created_at DESC);

ALTER TABLE review_decisions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS review_decisions_select ON review_decisions;
CREATE POLICY review_decisions_select ON review_decisions
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

DROP POLICY IF EXISTS review_decisions_write ON review_decisions;
CREATE POLICY review_decisions_write ON review_decisions
    FOR ALL TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

GRANT SELECT, INSERT, UPDATE, DELETE ON review_decisions TO authenticated;
