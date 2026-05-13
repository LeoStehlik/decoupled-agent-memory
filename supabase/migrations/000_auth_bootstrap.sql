SELECT 'CREATE DATABASE supabase_auth'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'supabase_auth')\gexec

\connect supabase_auth
CREATE SCHEMA IF NOT EXISTS auth;

\connect supavault
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS auth;

CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(
    NULLIF(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub',
    '00000000-0000-0000-0000-000000000000'
  )::uuid
$$;

CREATE TABLE IF NOT EXISTS auth.users (
    id UUID PRIMARY KEY,
    email TEXT,
    raw_user_meta_data JSONB DEFAULT '{}'::jsonb
);
