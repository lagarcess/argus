-- LangGraph checkpoint tables store runtime thread memory, not product records
-- meant for Supabase client access. Keep direct Postgres owner access for the
-- API checkpointer, but enable RLS in the exposed public schema and make the
-- browser-facing roles explicitly unable to read or mutate checkpoint rows.

revoke all on table public.checkpoint_blobs from public, anon, authenticated;
revoke all on table public.checkpoint_migrations from public, anon, authenticated;
revoke all on table public.checkpoint_writes from public, anon, authenticated;
revoke all on table public.checkpoints from public, anon, authenticated;

alter table public.checkpoint_blobs enable row level security;
alter table public.checkpoint_migrations enable row level security;
alter table public.checkpoint_writes enable row level security;
alter table public.checkpoints enable row level security;
