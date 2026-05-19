CREATE TABLE IF NOT EXISTS review_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  knowledge_base_id uuid NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  synthesis_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  action text NOT NULL CHECK (action IN ('proposed', 'applied', 'rejected')),
  actor text NOT NULL DEFAULT 'operator',
  rationale text,
  proposal_content text,
  diff_content text,
  proposal_sha256 text,
  linked_source_ids uuid[] NOT NULL DEFAULT '{}'::uuid[],
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_decisions_kb_created_at
  ON review_decisions (knowledge_base_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_review_decisions_user_created_at
  ON review_decisions (user_id, created_at DESC);

ALTER TABLE review_decisions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS review_decisions_select ON review_decisions;
CREATE POLICY review_decisions_select ON review_decisions
  FOR SELECT USING (user_id = auth.uid());

DROP POLICY IF EXISTS review_decisions_insert ON review_decisions;
CREATE POLICY review_decisions_insert ON review_decisions
  FOR INSERT WITH CHECK (user_id = auth.uid());

GRANT SELECT, INSERT ON review_decisions TO authenticated;
