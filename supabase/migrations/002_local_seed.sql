INSERT INTO auth.users (id, email, raw_user_meta_data)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'local-brain@example.invalid',
    '{"display_name":"Local Brain"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO public.users (id, email, display_name, onboarded)
VALUES (
    '11111111-1111-1111-1111-111111111111',
    'local-brain@example.invalid',
    'Local Brain',
    true
)
ON CONFLICT (id) DO NOTHING;
