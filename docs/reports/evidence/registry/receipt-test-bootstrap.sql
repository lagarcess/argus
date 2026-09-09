-- Dependency scaffold for a fresh, disposable PostgreSQL database only.
-- Apply the actual receipt migrations after this file; no trigger is copied here.
create role anon;
create role authenticated;
create schema auth;
create table auth.users(id uuid primary key, email text);
create table public.profiles(id uuid primary key references auth.users(id), email text, username text);
create table public.conversations(id uuid primary key, user_id uuid references profiles(id) on delete cascade, title text, deleted_at timestamptz);
create table public.messages(id uuid primary key, conversation_id uuid references conversations(id) on delete cascade, user_id uuid references profiles(id) on delete cascade, role text, content text, metadata jsonb);
create table public.backtest_runs(id uuid primary key);
create table public.evidence_artifacts(id uuid primary key);
