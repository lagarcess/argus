-- Durable once-only claims for guest funnel milestone events.
--
-- Milestone events are the acquisition funnel's numerator. A retry, a replay,
-- a reload, or two concurrent completions could each emit the same milestone
-- again, and duplicates inflate conversion counts in one direction, so every
-- decision read off that data is wrong the same way. The guarantee lives in a
-- primary key here rather than in application logic because a constraint
-- cannot drift and holds across processes, restarts, and workers.
--
-- subject_key is the visitor key that already meters guest allowances, not a
-- user id: a guest workspace renewal mints a fresh user id, so a user-keyed
-- milestone would re-fire on every renewal. Like visitor_usage_counters this
-- is deliberately opaque text and not FK-bound, because the subject is a
-- visitor we have no account for rather than a profile.
--
-- Rows expire. A milestone table keyed on a visitor digest with no cleanup
-- path becomes a durable visitor log. Retention outlives the seven-day guest
-- workspace with headroom and nothing more.

create table if not exists public.guest_funnel_milestones (
  subject_key text not null,
  milestone text not null,
  recorded_at timestamptz not null default now(),
  expires_at timestamptz not null,
  primary key (subject_key, milestone)
);

comment on table public.guest_funnel_milestones is
  'Once-per-subject funnel milestone claims. Not FK-bound: the subject is a visitor, not a profile.';

-- Purge scans by expiry alone.
create index if not exists guest_funnel_milestones_expiry_idx
  on public.guest_funnel_milestones (expires_at);

alter table public.guest_funnel_milestones enable row level security;

-- No policies: service_role bypasses RLS and nothing else may read or write
-- funnel claims. Enabling RLS without policies is the deny-all default.

revoke all on table public.guest_funnel_milestones from public, anon, authenticated;
grant select, insert, update, delete on table public.guest_funnel_milestones
  to service_role;


-- One claim attempt. Returns true only for the caller that recorded the
-- milestone, so a duplicate attempt is a silent no-op rather than an error.
--
-- An expired claim is taken over in the same statement. Retention must not
-- depend on the purge job having run: a stale row would otherwise suppress a
-- milestone the visitor legitimately reaches again.
create or replace function public.claim_guest_funnel_milestone(
  p_subject_key text,
  p_milestone text,
  p_expires_at timestamptz
)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_claimed boolean;
begin
  if p_subject_key is null or length(trim(p_subject_key)) = 0 then
    raise exception 'subject key is required';
  end if;
  if p_milestone is null or length(trim(p_milestone)) = 0 then
    raise exception 'milestone is required';
  end if;
  if p_expires_at is null then
    raise exception 'milestone expiry is required';
  end if;

  insert into public.guest_funnel_milestones (
    subject_key, milestone, expires_at
  ) values (
    p_subject_key, p_milestone, p_expires_at
  )
  on conflict (subject_key, milestone) do update set
    recorded_at = now(),
    expires_at = excluded.expires_at
  where public.guest_funnel_milestones.expires_at <= now()
  returning true into v_claimed;

  return coalesce(v_claimed, false);
end;
$$;

revoke all on function
  public.claim_guest_funnel_milestone(text, text, timestamptz)
  from public, anon, authenticated;
grant execute on function
  public.claim_guest_funnel_milestone(text, text, timestamptz)
  to service_role;


-- Bounded retention, mirroring purge_expired_visitor_usage.
create or replace function public.purge_expired_guest_funnel_milestones(
  p_before timestamptz default now()
)
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  v_deleted integer;
begin
  delete from public.guest_funnel_milestones where expires_at <= p_before;
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$$;

revoke all on function public.purge_expired_guest_funnel_milestones(timestamptz)
  from public, anon, authenticated;
grant execute on function public.purge_expired_guest_funnel_milestones(timestamptz)
  to service_role;
