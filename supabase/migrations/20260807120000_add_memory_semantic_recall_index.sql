-- Derivative semantic index for personalization-memory recall.
--
-- This table is not canonical truth. It holds vectors and the confirmed text
-- of memories that already exist in public.memory_records, plus the canonical
-- record id that joins the two. Dropping it costs recall quality and never
-- costs a memory: retrieval falls back to the canonical token match.
--
-- Owning the shape here rather than letting the client issue DDL means the API
-- service never needs CREATE privileges at runtime, and the column types stay
-- reviewable. The shape matches what the Mem0 pgvector store expects, so its
-- own "if not exists" statements are no-ops against this table.
--
-- Like every other memory table, this is private backend state: Browser and
-- Data API roles, including service_role, have no direct access.

create extension if not exists vector;

create table if not exists public.argus_memory_vectors (
  id uuid primary key,
  vector vector(1024),
  payload jsonb
);

-- Cosine operator class: the store searches with the `<=>` distance operator.
create index if not exists argus_memory_vectors_hnsw_idx
  on public.argus_memory_vectors
  using hnsw (vector vector_cosine_ops);

create index if not exists argus_memory_vectors_text_lemmatized_idx
  on public.argus_memory_vectors
  using gin (to_tsvector('simple', payload ->> 'text_lemmatized'));

alter table public.argus_memory_vectors enable row level security;
alter table public.argus_memory_vectors force row level security;

revoke all on table public.argus_memory_vectors
  from public, anon, authenticated, service_role;
