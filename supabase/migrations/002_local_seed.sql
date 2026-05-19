-- No default service user is seeded.
-- Trusted local agents should map STATIC_BEARER_TOKEN to a real browser-visible
-- user UUID through LOCAL_USER_ID in .env. Hidden service users create invisible
-- workspaces and make agent-written pages hard to inspect in the UI.

DO $$
BEGIN
  RAISE NOTICE 'No local service user seeded; configure LOCAL_USER_ID explicitly.';
END
$$;
