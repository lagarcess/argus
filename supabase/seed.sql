-- Non-secret QA fixtures for local Supabase stacks and isolated QA branches.
-- Never add passwords, tokens, keys, or production data to this file.
-- Auth users are created at runtime by scripts/qa/setup-local-identities.sh;
-- this seed only guarantees the Argus private-alpha allowlist admits them.

insert into public.private_alpha_allowlist (email)
values
  ('qa-recovery-248@qa.argus.local'),
  ('qa-second-248@qa.argus.local')
on conflict (email) do nothing;
