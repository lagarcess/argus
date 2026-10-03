-- Lane 6: in-app account deletion.
-- Spec: docs/specs/lanes/mvee-five-lane-handoff.md#lane-6-account-deletion
-- Census: docs/specs/lanes/account-deletion-fk-census.md
-- Design: Marcus's Lane 6 design note on #791, with Lucas's Oct 2 overrides.
--
-- What this adds:
--   1. The composite owner keys the deletion re-keys become DEFERRABLE
--      INITIALLY IMMEDIATE. Today's writers see no change: only the deletion
--      definers defer them, and they set every constraint immediate before
--      they return. ON DELETE actions are unchanged, and Postgres keeps
--      RESTRICT immediate on a deferrable key.
--   2. household_plan_participants.joined_at, the seniority the plan handover
--      uses (#787). A re-grant resets it.
--   3. household_members.former_member_number for the "Exmiembro" placeholder.
--   4. argus_private.account_placeholders, the run record, its in-flight
--      placeholder map and its pending revocations.
--   5. The auth.users triggers skip placeholders.
--   6. The Household-owned invite function and the deletion definers.
--
-- Placeholders (Yelena, HoE, Oct 2, 11:06 PM CT rule, matching #796): one per
-- (household or standalone shared group, departed person); every plan and
-- membership-keyed row of the person in one household goes to that
-- household's placeholder. Each is a nameless auth.users row created through
-- the Supabase Admin API as `exmiembro+<random uuid>@cuadrao.invalid`, email
-- confirmed, app_metadata {"placeholder": true}, user metadata {}, no phone,
-- no password, banned by ban_duration (GoTrue sets banned_until). Decision
-- 17's "no user id" means no id tied to the person: the FKs need a real
-- auth.users row. Never DML on auth.users here.
--
-- Method: move in place under the DEFERRABLE INITIALLY IMMEDIATE keys, plus
-- account copies (one per scope), not copy, re-point, delete. Deferral does
-- not relax three row rules, so each statement must satisfy them:
--   * shared claim must retain its canonical binding (shared_claim_binding):
--     financial_plan_links.user_id is the binding owner, so a binding moves
--     before its claims;
--   * shared allocation must retain true owner and consent
--     (shared_allocation_binding on financial_goal_allocations);
--   * financial_record_revisions.reversal_of_owner_id is generated and
--     changes only through details, which the writer rewrites.

-- 1. Keys the deletion re-keys ------------------------------------------------

alter table public.household_plan_bindings
    alter constraint household_plan_bindings_budget_id_owner_user_id_fkey deferrable initially immediate,
    alter constraint household_plan_bindings_expectation_id_owner_user_id_fkey deferrable initially immediate,
    alter constraint household_plan_bindings_goal_id_owner_user_id_fkey deferrable initially immediate,
    alter constraint household_plan_bindings_debt_plan_id_owner_user_id_fkey deferrable initially immediate,
    alter constraint household_plan_bindings_kind_definition_id_owner_user_id_f_fkey deferrable initially immediate,
    alter constraint household_plan_bindings_kind_definition_id_owner_user_id_r_fkey deferrable initially immediate,
    alter constraint household_plan_bindings_owner_membership_id_household_id_o_fkey deferrable initially immediate;

alter table public.financial_plan_links
    alter constraint financial_plan_links_budget_id_user_id_fkey deferrable initially immediate,
    alter constraint financial_plan_links_expectation_id_user_id_fkey deferrable initially immediate,
    alter constraint financial_plan_links_goal_id_user_id_fkey deferrable initially immediate,
    alter constraint financial_plan_links_debt_plan_id_user_id_fkey deferrable initially immediate,
    alter constraint financial_plan_links_binding_id_user_id_fkey deferrable initially immediate,
    alter constraint financial_plan_links_activity_id_activity_revision_activit_fkey deferrable initially immediate;

alter table public.financial_goal_allocations
    alter constraint financial_goal_allocations_goal_id_goal_owner_id_fkey deferrable initially immediate,
    alter constraint financial_goal_allocations_binding_id_goal_owner_id_fkey deferrable initially immediate;

alter table public.financial_goal_allocation_revisions
    alter constraint financial_goal_allocation_revisions_goal_id_goal_owner_id_fkey deferrable initially immediate,
    alter constraint financial_goal_allocation_revi_account_id_account_owner_id_fkey deferrable initially immediate;

alter table public.financial_plan_responsibilities
    alter constraint financial_plan_responsibiliti_kind_definition_id_owner_id__fkey deferrable initially immediate;

alter table public.financial_debt_plans
    alter constraint financial_debt_plans_debt_account_id_user_id_fkey deferrable initially immediate;

alter table public.financial_records
    alter constraint financial_records_account_id_user_id_fkey deferrable initially immediate;

alter table public.financial_record_revisions
    alter constraint financial_record_revisions_record_id_user_id_fkey deferrable initially immediate,
    alter constraint financial_purchase_revision_owner_fk deferrable initially immediate;

alter table public.financial_activity_revisions
    alter constraint financial_activity_revisions_activity_id_user_id_fkey deferrable initially immediate;

alter table public.financial_activity_memberships
    alter constraint financial_activity_membership_revision_fk deferrable initially immediate,
    alter constraint financial_activity_memberships_activity_id_user_id_fkey deferrable initially immediate;

alter table public.household_plan_archived_claims
    alter constraint household_plan_archived_claim_activity_id_activity_revisio_fkey deferrable initially immediate;

alter table public.household_plan_archived_activities
    alter constraint household_plan_archived_activ_activity_id_activity_revisio_fkey deferrable initially immediate;

-- 2. Plan seniority --------------------------------------------------------------

alter table public.household_plan_participants add column joined_at timestamptz;

update public.household_plan_participants p
   set joined_at = r.recorded_at
  from public.household_plan_bindings b
  join public.financial_plan_definition_revisions r
    on r.kind = b.kind
   and r.definition_id = b.definition_id
   and r.owner_id = b.owner_user_id
 where b.id = p.binding_id
   and r.revision = p.granted_revision;

do $$
begin
  if exists (select 1 from public.household_plan_participants where joined_at is null) then
    raise exception 'household_plan_participants.granted_revision does not resolve to a plan revision'
      using errcode = '23514';
  end if;
end;
$$;

alter table public.household_plan_participants
    alter column joined_at set default now(),
    alter column joined_at set not null;

-- A re-grant (a new granted_revision, or a revoked row made active again)
-- resets seniority, the same rule planning_store.replace_participants follows.
create function argus_private.reset_plan_participant_seniority()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.granted_revision is distinct from old.granted_revision
     or (old.revoked_at is not null and new.revoked_at is null) then
    new.joined_at := now();
  end if;
  return new;
end;
$$;

revoke all on function argus_private.reset_plan_participant_seniority()
  from public, anon, authenticated;

create trigger reset_plan_participant_seniority
before update on public.household_plan_participants
for each row execute function argus_private.reset_plan_participant_seniority();

-- 3. The former-member placeholder ------------------------------------------------

-- One placeholder membership per (household, deleted person). The number
-- orders a household's former members; plan reads show "Exmiembro" when a
-- plan has one former member and "Exmiembro 1", "Exmiembro 2" when it has
-- several, numbered within that plan.
alter table public.household_members
    add column former_member_number smallint check (former_member_number > 0);

create unique index household_members_former_member_number_idx
    on public.household_members (household_id, former_member_number)
    where former_member_number is not null;

-- 4. Placeholders and the run record ---------------------------------------------------

-- Every placeholder ever created. No link to the person: no unit, no hash.
-- The row is written before the Admin API creates the auth user, so the API
-- and the auth triggers already treat that id as a placeholder. No FK: the id
-- is reserved before the user exists.
create table argus_private.account_placeholders (
    id uuid primary key,
    created_at timestamptz not null default now()
);

-- The resumable run. user_id is held only while the run is in flight, with a
-- unique constraint so a retry finds the same run and reuses its placeholders.
-- It is cleared once the auth user is gone. After that the row keeps only the
-- hash, the analytics distinct id (already a hash), the status and the counts.
create table argus_private.account_deletion_runs (
    subject_hash text primary key check (subject_hash ~ '^[0-9a-f]{64}$'),
    user_id uuid unique,
    analytics_distinct_id text not null,
    status text not null default 'started'
        check (status in ('started', 'data_deleted', 'done')),
    steps jsonb not null default '{}'::jsonb check (jsonb_typeof(steps) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    check ((status in ('started', 'data_deleted')) = (user_id is not null))
);

-- The in-flight map from the run to its placeholders: one per sharing scope.
-- A household is one scope, so every plan and membership-keyed row of the
-- person inside one household moves to that household's single placeholder.
-- An activity group shared outside any plan belongs to no household and gets
-- its own. No placeholder spans two scopes. Scrubbed when the run completes.
create table argus_private.account_deletion_placeholders (
    subject_hash text not null
        references argus_private.account_deletion_runs (subject_hash) on delete cascade,
    scope_kind text not null check (scope_kind in ('household', 'group')),
    scope_id uuid not null,
    placeholder_id uuid not null unique
        references argus_private.account_placeholders (id),
    created boolean not null default false,
    used boolean not null default false,
    primary key (subject_hash, scope_kind, scope_id)
);

-- A revocation still owed to a provider. The encrypted credential is held
-- here, not on the connection row, so it survives the account delete, and it
-- is dropped as soon as the provider confirms. 'gmail' rows are every Google
-- token Cuadrao holds: the Gmail source's sealed refresh tokens. Google
-- sign-in through Supabase leaves no provider token with us.
-- Every revocation settles before the account delete (step 7). 'unrecoverable'
-- is a credential sealed under a key no longer held: it can never be opened,
-- so its ciphertext is dropped and the run goes on.
create table argus_private.account_deletion_revocations (
    subject_hash text not null
        references argus_private.account_deletion_runs (subject_hash) on delete cascade,
    provider text not null check (provider in ('gmail', 'plaid', 'apple')),
    source_ref uuid not null,
    external_ref text,
    secret_ciphertext bytea,
    status text not null default 'pending'
        check (status in ('pending', 'revoked', 'unrecoverable')),
    attempts integer not null default 0 check (attempts >= 0),
    last_error text check (char_length(last_error) <= 200),
    updated_at timestamptz not null default now(),
    primary key (subject_hash, provider, source_ref),
    check (status = 'pending' or (secret_ciphertext is null and external_ref is null))
);

-- Events this lane owns. Updates (slot 7) reads them as its source. No amounts
-- and no names: the reader resolves the plan name at read time.
create table public.household_deletion_events (
    id uuid primary key default gen_random_uuid(),
    household_id uuid not null references public.households (id) on delete cascade,
    recipient_membership_id uuid not null references public.household_members (id) on delete cascade,
    binding_id uuid references public.household_plan_bindings (id) on delete cascade,
    kind text not null check (kind in ('member_deleted', 'plan_handed_over', 'responsibilities_returned')),
    created_at timestamptz not null default now()
);

create index household_deletion_events_recipient_idx
    on public.household_deletion_events (recipient_membership_id, created_at desc);

alter table public.household_deletion_events enable row level security;
revoke all on public.household_deletion_events from public, anon, authenticated;
grant select, insert on public.household_deletion_events to service_role;

alter table argus_private.account_placeholders enable row level security;
alter table argus_private.account_deletion_runs enable row level security;
alter table argus_private.account_deletion_placeholders enable row level security;
alter table argus_private.account_deletion_revocations enable row level security;
revoke all on argus_private.account_placeholders,
    argus_private.account_deletion_runs,
    argus_private.account_deletion_placeholders,
    argus_private.account_deletion_revocations
  from public, anon, authenticated;
grant select, insert, delete on argus_private.account_placeholders to service_role;
grant select, insert, update on argus_private.account_deletion_runs to service_role;
grant select, insert, update, delete on argus_private.account_deletion_placeholders to service_role;
grant select, insert, update, delete on argus_private.account_deletion_revocations to service_role;

-- 5. auth.users triggers skip placeholders ---------------------------------------------

create function argus_private.is_account_placeholder(p_id uuid, p_app_metadata jsonb)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(p_app_metadata ->> 'placeholder', '') = 'true'
      or exists (select 1 from argus_private.account_placeholders t where t.id = p_id);
$$;

revoke all on function argus_private.is_account_placeholder(uuid, jsonb)
  from public, anon, authenticated;
grant execute on function argus_private.is_account_placeholder(uuid, jsonb) to service_role;

-- The triggers test app_metadata only. GoTrue writes auth.users as
-- supabase_auth_admin, which has no access to argus_private, so a WHEN clause
-- calling the function above fails every sign-up. app_metadata is writable only
-- with the service role, and every placeholder is created with
-- {"placeholder": true} after its id is registered.
drop trigger if exists bind_guest_signup_handoff on auth.users;
create trigger bind_guest_signup_handoff
after insert on auth.users
for each row
when (coalesce(new.raw_app_meta_data ->> 'placeholder', '') <> 'true')
execute function argus_private.bind_guest_signup_handoff();

drop trigger if exists finalize_linked_guest_identity on auth.users;
create trigger finalize_linked_guest_identity
after update of email, is_anonymous on auth.users
for each row
when (coalesce(new.raw_app_meta_data ->> 'placeholder', '') <> 'true')
execute function argus_private.finalize_linked_guest_identity();

-- 6a. Household-owned invite cleanup (step 4, decision 3) ------------------------------

-- The only writer Lane 6 uses on the invite tables. It clears the person's live
-- ids, keeps every anonymous row, and rotates sender_ref: a distinct fresh
-- sender_ref per row; inviter_origin_id chain unchanged (Priya, Oct 3). No
-- value left groups the person's invites, which intentionally ends the
-- per-user count for them. It revokes their unused beta invites and writes no
-- event. Idempotent.
create function argus_private.forget_invite_party(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_ref uuid;
begin
  if p_user_id is null then
    raise exception 'account_deletion_user_required' using errcode = '22023';
  end if;
  select ref into v_ref from public.invite_sender_refs where user_id = p_user_id;
  update public.invite_referrals
     set sender_ref = gen_random_uuid()  -- volatile: a new value for each row
   where sender_user_id = p_user_id
      or (v_ref is not null and sender_ref = v_ref);
  update public.invite_referrals set sender_user_id = null where sender_user_id = p_user_id;
  update public.invite_referrals set acceptor_user_id = null where acceptor_user_id = p_user_id;
  delete from public.invite_sender_refs where user_id = p_user_id;
  update public.beta_invitations
     set revoked_at = now()
   where created_by = p_user_id
     and kind = 'beta'
     and revoked_at is null
     and use_count < max_uses;
  update public.beta_invitations set created_by = null where created_by = p_user_id;
  update public.beta_invite_quota_grants set granted_by = null where granted_by = p_user_id;
  update public.household_invitations set created_by = null where created_by = p_user_id;
  update public.household_invitations set accepted_by = null where accepted_by = p_user_id;
end;
$$;

revoke all on function argus_private.forget_invite_party(uuid) from public, anon, authenticated;
grant execute on function argus_private.forget_invite_party(uuid) to service_role;

-- 6b. Deletion definers -----------------------------------------------------------------

-- Every key above, deferred for one definer call. Callers end with
-- `set constraints all immediate`, so a violation raises inside the call.
create function argus_private.defer_deletion_keys()
returns void
language plpgsql
set search_path = ''
as $$
begin
  set constraints
    public.household_plan_bindings_budget_id_owner_user_id_fkey,
    public.household_plan_bindings_expectation_id_owner_user_id_fkey,
    public.household_plan_bindings_goal_id_owner_user_id_fkey,
    public.household_plan_bindings_debt_plan_id_owner_user_id_fkey,
    public.household_plan_bindings_kind_definition_id_owner_user_id_f_fkey,
    public.household_plan_bindings_kind_definition_id_owner_user_id_r_fkey,
    public.household_plan_bindings_owner_membership_id_household_id_o_fkey,
    public.financial_plan_links_budget_id_user_id_fkey,
    public.financial_plan_links_expectation_id_user_id_fkey,
    public.financial_plan_links_goal_id_user_id_fkey,
    public.financial_plan_links_debt_plan_id_user_id_fkey,
    public.financial_plan_links_binding_id_user_id_fkey,
    public.financial_plan_links_activity_id_activity_revision_activit_fkey,
    public.financial_goal_allocations_goal_id_goal_owner_id_fkey,
    public.financial_goal_allocations_binding_id_goal_owner_id_fkey,
    public.financial_goal_allocation_revisions_goal_id_goal_owner_id_fkey,
    public.financial_goal_allocation_revi_account_id_account_owner_id_fkey,
    public.financial_plan_responsibiliti_kind_definition_id_owner_id__fkey,
    public.financial_debt_plans_debt_account_id_user_id_fkey,
    public.financial_records_account_id_user_id_fkey,
    public.financial_record_revisions_record_id_user_id_fkey,
    public.financial_purchase_revision_owner_fk,
    public.financial_activity_revisions_activity_id_user_id_fkey,
    public.financial_activity_membership_revision_fk,
    public.financial_activity_memberships_activity_id_user_id_fkey,
    public.household_plan_archived_claim_activity_id_activity_revisio_fkey,
    public.household_plan_archived_activ_activity_id_activity_revisio_fkey,
    public.financial_activity_current_revision_fk,
    public.financial_activity_original_record_revision,
    public.financial_payment_return_original_owner_fk
  deferred;
end;
$$;

revoke all on function argus_private.defer_deletion_keys() from public, anon, authenticated;

-- A re-key at deletion is not a plan edit: when the deletion writer moves a
-- debt plan to its placeholder's copy of the debt account, the canonical row
-- changes without a new revision. Otherwise identical to 20261002040000.
create or replace function public.record_plan_definition_revision() returns trigger language plpgsql
set search_path = '' as $$
begin
 if TG_OP='UPDATE' and OLD.body=NEW.body then return NEW; end if;
 if TG_OP='UPDATE' and current_setting('argus.locked_history_writer', true) = 'deletion'
    and (NEW.body->>'version') = (OLD.body->>'version') then
  return NEW;
 end if;
 if TG_OP='UPDATE' and (NEW.body->>'version')::integer <= (OLD.body->>'version')::integer then
  raise exception 'canonical definition revision must advance' using errcode='23514';
 end if;
 insert into public.financial_plan_definition_revisions(kind,definition_id,owner_id,revision,body,actor_id)
 values(TG_ARGV[0],NEW.id,NEW.user_id,(NEW.body->>'version')::integer,NEW.body,
 nullif(current_setting('argus.plan_actor',true),'')::uuid);
 if TG_OP='UPDATE' then
  insert into public.financial_plan_responsibilities
   select kind,definition_id,owner_id,(NEW.body->>'version')::integer,
    membership_id,amount_minor,period,occurrence_id,schedule_id,agreed_date
   from public.financial_plan_responsibilities
   where kind=TG_ARGV[0] and definition_id=NEW.id and owner_id=NEW.user_id
    and revision=(OLD.body->>'version')::integer;
 end if;
 return NEW;
end $$;

create function argus_private.require_deletion_writer()
returns void
language plpgsql
set search_path = ''
as $$
begin
  if coalesce(current_setting('argus.locked_history_writer', true), '') <> 'deletion' then
    raise exception 'account_deletion_writer_required' using errcode = '42501';
  end if;
end;
$$;

revoke all on function argus_private.require_deletion_writer() from public, anon, authenticated;

-- Moves one binding, its definition, revisions, responsibilities, claims and
-- allocations from one owner to another (step 1.2, a #773 archive in step 5.2,
-- or a plan's own placeholder in step 5.1). The definition keeps its id, so it
-- moves in place under the deferred keys. Locked history is rewritten only here.
create function argus_private.deletion_rekey_binding(
  p_binding_id uuid,
  p_from uuid,
  p_to uuid,
  p_to_membership_id uuid,
  p_debt_account_id uuid default null
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_binding public.household_plan_bindings%rowtype;
begin
  perform argus_private.require_deletion_writer();
  select * into v_binding
    from public.household_plan_bindings
   where id = p_binding_id and owner_user_id = p_from
   for update;
  if not found then
    raise exception 'account_deletion_binding_not_found' using errcode = 'P0002';
  end if;
  if exists (
    select 1 from public.household_plan_bindings
     where kind = v_binding.kind and definition_id = v_binding.definition_id
       and owner_user_id = p_from and id <> p_binding_id and revoked_at is null
  ) then
    raise exception 'account_deletion_definition_bound_twice' using errcode = '55000';
  end if;
  perform argus_private.defer_deletion_keys();
  -- The binding moves first: the claim and allocation triggers check every
  -- moved row against the binding's owner.
  update public.household_plan_bindings
     set owner_user_id = p_to, owner_membership_id = p_to_membership_id
   where id = p_binding_id;

  if v_binding.kind = 'budget' then
    update public.financial_budgets set user_id = p_to where id = v_binding.definition_id and user_id = p_from;
    update public.financial_plan_links set user_id = p_to where budget_id = v_binding.definition_id and user_id = p_from;
  elsif v_binding.kind = 'bill' then
    update public.financial_expectations set user_id = p_to where id = v_binding.definition_id and user_id = p_from;
    update public.financial_plan_links set user_id = p_to where expectation_id = v_binding.definition_id and user_id = p_from;
  elsif v_binding.kind = 'goal' then
    update public.financial_goals set user_id = p_to where id = v_binding.definition_id and user_id = p_from;
    update public.financial_plan_links set user_id = p_to where goal_id = v_binding.definition_id and user_id = p_from;
  elsif v_binding.kind = 'debt' then
    -- financial_debt_plans cascades from its owner's debt account, so a debt
    -- plan moves together with that account (or the account's placeholder copy).
    update public.financial_debt_plans
       set user_id = p_to,
           debt_account_id = coalesce(p_debt_account_id, debt_account_id),
           body = case when p_debt_account_id is null then body
                       else jsonb_set(body, '{debt_account_id}', to_jsonb(p_debt_account_id::text)) end
     where id = v_binding.definition_id and user_id = p_from;
    update public.financial_plan_links set user_id = p_to where debt_plan_id = v_binding.definition_id and user_id = p_from;
  end if;
  update public.financial_plan_definition_revisions
     set owner_id = p_to,
         body = case when v_binding.kind = 'debt' and p_debt_account_id is not null and body ? 'debt_account_id'
                     then jsonb_set(body, '{debt_account_id}', to_jsonb(p_debt_account_id::text))
                     else body end
   where kind = v_binding.kind and definition_id = v_binding.definition_id and owner_id = p_from;
  update public.financial_plan_responsibilities
     set owner_id = p_to
   where kind = v_binding.kind and definition_id = v_binding.definition_id and owner_id = p_from;
  update public.financial_plan_links set user_id = p_to where binding_id = p_binding_id and user_id = p_from;
  if v_binding.kind = 'goal' then
    update public.financial_goal_allocations
       set goal_owner_id = p_to
     where goal_id = v_binding.definition_id and goal_owner_id = p_from;
    update public.financial_goal_allocation_revisions
       set goal_owner_id = p_to
     where goal_id = v_binding.definition_id and goal_owner_id = p_from;
  end if;
  -- The new owner is no longer a participant of their own plan.
  delete from public.household_plan_participants
   where binding_id = p_binding_id and membership_id = p_to_membership_id;
end;
$$;

revoke all on function argus_private.deletion_rekey_binding(uuid, uuid, uuid, uuid, uuid)
  from public, anon, authenticated;

-- Deletes one plan binding the person owns that nobody else is in (step 5.2).
create function argus_private.deletion_drop_binding(p_binding_id uuid, p_owner uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  perform argus_private.require_deletion_writer();
  if not exists (
    select 1 from public.household_plan_bindings where id = p_binding_id and owner_user_id = p_owner
  ) then
    raise exception 'account_deletion_binding_not_found' using errcode = 'P0002';
  end if;
  delete from public.household_plan_archived_claims where binding_id = p_binding_id;
  delete from public.household_plan_archived_activities where binding_id = p_binding_id;
  delete from public.household_plan_archived_allocations where binding_id = p_binding_id;
  delete from public.household_plan_receipts where binding_id = p_binding_id;
  delete from public.household_plan_participants where binding_id = p_binding_id;
  delete from public.financial_plan_links where binding_id = p_binding_id;
  delete from public.financial_goal_allocations where binding_id = p_binding_id;
  delete from public.financial_goal_allocation_revisions where binding_id = p_binding_id;
  delete from public.household_plan_bindings where id = p_binding_id;
end;
$$;

revoke all on function argus_private.deletion_drop_binding(uuid, uuid)
  from public, anon, authenticated;

-- Step 1.2 for one household: each live shared plan the person owns passes to
-- its longest-standing active participant (earliest joined_at, then the lowest
-- membership id). Plans nobody else is in are deleted (step 5.2). Shared debt
-- plans stay with the person here: the leave archives them read-only, and step
-- 5.1 moves that archive, with its debt account, to the plan's own placeholder
-- (Lucas, Oct 2). Returns the handed
-- over bindings and their new owner memberships, for the new-owner notices.
create function argus_private.deletion_hand_over_plans(p_user_id uuid, p_household_id uuid)
returns table (binding_id uuid, new_owner_membership_id uuid)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_binding record;
  v_successor record;
begin
  perform argus_private.require_deletion_writer();
  for v_binding in
    select b.id, b.kind
      from public.household_plan_bindings b
     where b.household_id = p_household_id and b.owner_user_id = p_user_id
       and b.revoked_at is null and b.departed_at is null
     order by b.id
     for update
  loop
    select p.membership_id, m.user_id into v_successor
      from public.household_plan_participants p
      join public.household_members m on m.id = p.membership_id
     where p.binding_id = v_binding.id and p.revoked_at is null
       and m.left_at is null and m.user_id <> p_user_id
     order by p.joined_at, p.membership_id
     limit 1;
    if not found then
      perform argus_private.deletion_drop_binding(v_binding.id, p_user_id);
    elsif v_binding.kind <> 'debt' then
      perform argus_private.deletion_rekey_binding(
        v_binding.id, p_user_id, v_successor.user_id, v_successor.membership_id
      );
      binding_id := v_binding.id;
      new_owner_membership_id := v_successor.membership_id;
      return next;
    end if;
  end loop;
  set constraints all immediate;
end;
$$;

revoke all on function argus_private.deletion_hand_over_plans(uuid, uuid)
  from public, anon, authenticated;

-- Step 5.2 for #773 archives an earlier departure left: each departed binding
-- the person owns passes, still read-only, to its longest-standing participant
-- among those not revoked at departure who are still members. If there is
-- none, the binding and its archive are deleted.
create function argus_private.deletion_pass_on_archives(p_user_id uuid)
returns table (binding_id uuid, new_owner_membership_id uuid)
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_binding record;
  v_successor record;
begin
  perform argus_private.require_deletion_writer();
  for v_binding in
    select b.id, b.kind, b.departed_at
      from public.household_plan_bindings b
     where b.owner_user_id = p_user_id and b.revoked_at is null
       and b.departed_at is not null and b.kind <> 'debt'
       and b.departed_at < now()
     order by b.id
     for update
  loop
    select p.membership_id, m.user_id into v_successor
      from public.household_plan_participants p
      join public.household_members m on m.id = p.membership_id
     where p.binding_id = v_binding.id
       and (p.revoked_at is null or p.revoked_at > v_binding.departed_at)
       and m.left_at is null and m.user_id <> p_user_id
     order by p.joined_at, p.membership_id
     limit 1;
    if not found then
      perform argus_private.deletion_drop_binding(v_binding.id, p_user_id);
    else
      perform argus_private.deletion_rekey_binding(
        v_binding.id, p_user_id, v_successor.user_id, v_successor.membership_id
      );
      binding_id := v_binding.id;
      new_owner_membership_id := v_successor.membership_id;
      return next;
    end if;
  end loop;
  set constraints all immediate;
end;
$$;

revoke all on function argus_private.deletion_pass_on_archives(uuid)
  from public, anon, authenticated;

-- The units that need a placeholder: every plan binding that holds any of the
-- person's rows, and every activity group that crosses owners outside those
-- plans. Read before the transaction so the Admin API can create one
-- placeholder per unit. It is a superset: unused placeholders are deleted.
create function argus_private.deletion_placeholder_units(p_user_id uuid)
returns table (unit_kind text, unit_id uuid, scope_kind text, scope_id uuid)
language sql
stable
security definer
set search_path = ''
as $$
  with mids as (
    select id from public.household_members where user_id = p_user_id
  ),
  plans as (
    select l.binding_id as id from public.financial_plan_links l
     where l.binding_id is not null
       and (l.activity_owner_id = p_user_id or l.contributor_membership_id in (select id from mids))
    union select binding_id from public.household_plan_archived_claims where activity_owner_id = p_user_id
    union select binding_id from public.household_plan_archived_activities where activity_owner_id = p_user_id
    union select binding_id from public.financial_goal_allocation_revisions
     where binding_id is not null
       and (account_owner_id = p_user_id or contributor_membership_id in (select id from mids))
    union select binding_id from public.household_plan_participants where membership_id in (select id from mids)
    union select b.id from public.household_plan_bindings b
     where b.revoked_at is null and exists (
       select 1 from public.financial_plan_responsibilities r
        where r.kind = b.kind and r.definition_id = b.definition_id
          and r.owner_id = b.owner_user_id and r.membership_id in (select id from mids))
    union select id from public.household_plan_bindings
     where owner_user_id = p_user_id and revoked_at is null and kind = 'debt'
  ),
  planned as (
    select l.activity_id from public.financial_plan_links l
     where l.activity_owner_id = p_user_id and l.binding_id in (select id from plans)
    union select activity_id from public.household_plan_archived_claims where activity_owner_id = p_user_id
    union select activity_id from public.household_plan_archived_activities where activity_owner_id = p_user_id
  ),
  groups as (
    select m.activity_id as id from public.financial_activity_memberships m
     where m.user_id = p_user_id and m.record_owner_id <> p_user_id
       and m.activity_id not in (select activity_id from planned)
    union
    select m.activity_id from public.financial_activity_memberships m
     where m.user_id <> p_user_id and m.record_owner_id = p_user_id
  )
  select 'plan'::text, p.id, 'household'::text, b.household_id
    from plans p join public.household_plan_bindings b on b.id = p.id
  union all
  -- A group a household plan claims or archives belongs to that household's
  -- scope (the plan's link names its legs and accounts); any other group is
  -- shared outside a plan and is its own scope.
  select 'group'::text, g.id,
         case when h.household_id is null then 'group' else 'household' end,
         coalesce(h.household_id, g.id)
    from groups g
    left join lateral (
      select b.household_id from public.household_plan_bindings b
       where b.id in (
         select binding_id from public.financial_plan_links where activity_id = g.id and binding_id is not null
         union select binding_id from public.household_plan_archived_claims where activity_id = g.id
         union select binding_id from public.household_plan_archived_activities where activity_id = g.id)
       order by b.household_id limit 1
    ) h on true;
$$;

revoke all on function argus_private.deletion_placeholder_units(uuid)
  from public, anon, authenticated;
grant execute on function argus_private.deletion_placeholder_units(uuid) to service_role;

-- Rewrites ids inside a jsonb document (claim attribution, record details).
create function argus_private.deletion_rewrite_ids(p_doc jsonb, p_from uuid[], p_to uuid[])
returns jsonb
language plpgsql
immutable
set search_path = ''
as $$
declare
  v_text text := p_doc::text;
  i integer;
begin
  if p_doc is null or p_from is null then
    return p_doc;
  end if;
  for i in 1 .. coalesce(array_length(p_from, 1), 0) loop
    v_text := replace(v_text, p_from[i]::text, p_to[i]::text);
  end loop;
  return v_text::jsonb;
end;
$$;

revoke all on function argus_private.deletion_rewrite_ids(jsonb, uuid[], uuid[])
  from public, anon, authenticated;

-- Step 5.1 for one unit. Copies the person's rows that the unit pins under the
-- unit's own placeholder, re-points the unit's children to the copies, and
-- leaves the originals to go with the person. Kept copies hold amount, date,
-- category and currency only: notes and source ids are dropped, account
-- nicknames cleared, and recorded_by nulled. Returns true if the unit used its
-- placeholder.
create function argus_private.deletion_place_unit(
  p_user_id uuid,
  p_unit_kind text,
  p_unit_id uuid,
  p_placeholder_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_binding public.household_plan_bindings%rowtype;
  v_member public.household_members%rowtype;
  v_placeholder_mid uuid;
  v_number integer;
  v_participant public.household_plan_participants%rowtype;
  v_debt_copy uuid;
  v_from uuid[];
  v_to uuid[];
  v_used boolean := false;
begin
  perform argus_private.require_deletion_writer();
  if not exists (select 1 from argus_private.account_placeholders where id = p_placeholder_id)
     or not exists (select 1 from auth.users where id = p_placeholder_id) then
    raise exception 'account_deletion_placeholder_missing' using errcode = 'P0002';
  end if;
  perform argus_private.defer_deletion_keys();

  -- One id map per placeholder for the whole transaction, shared by every
  -- kind: a single-leg activity has its record's id, so the copies must too.
  -- Two plans in one household that pin the same activity share one copy.
  create temp table if not exists deletion_id_map (placeholder_id uuid, old_id uuid, new_id uuid not null, primary key (placeholder_id, old_id)) on commit drop;
  create temp table if not exists deletion_copied (placeholder_id uuid, kind text, old_id uuid, primary key (placeholder_id, kind, old_id)) on commit drop;
  create temp table if not exists deletion_unit_ids (kind text, old_id uuid, primary key (kind, old_id)) on commit drop;
  create temp table if not exists deletion_fresh_ids (kind text, old_id uuid, primary key (kind, old_id)) on commit drop;
  truncate pg_temp.deletion_unit_ids, pg_temp.deletion_fresh_ids;

  if p_unit_kind = 'plan' then
    select * into v_binding from public.household_plan_bindings where id = p_unit_id for update;
    if not found then
      return false;
    end if;
    insert into pg_temp.deletion_unit_ids
    select 'activity', a from (
      select l.activity_id as a from public.financial_plan_links l
       where l.binding_id = p_unit_id and l.activity_owner_id = p_user_id
      union select activity_id from public.household_plan_archived_claims
       where binding_id = p_unit_id and activity_owner_id = p_user_id
      union select activity_id from public.household_plan_archived_activities
       where binding_id = p_unit_id and activity_owner_id = p_user_id
    ) s
    on conflict do nothing;
    insert into pg_temp.deletion_unit_ids
    select 'account', a from (
      select account_id as a from public.financial_goal_allocation_revisions
       where binding_id = p_unit_id and account_owner_id = p_user_id
      union
      select d.debt_account_id from public.financial_debt_plans d
       where v_binding.kind = 'debt' and v_binding.owner_user_id = p_user_id
         and d.id = v_binding.definition_id and d.user_id = p_user_id
    ) s
    where a is not null
    on conflict do nothing;
  elsif p_unit_kind = 'group' then
    if exists (select 1 from public.financial_activity_groups where id = p_unit_id and user_id = p_user_id) then
      insert into pg_temp.deletion_unit_ids values ('activity', p_unit_id) on conflict do nothing;
    else
      insert into pg_temp.deletion_unit_ids
      select distinct 'record', m.record_id from public.financial_activity_memberships m
       where m.activity_id = p_unit_id and m.record_owner_id = p_user_id
      on conflict do nothing;
    end if;
  else
    raise exception 'account_deletion_unit_invalid' using errcode = '22023';
  end if;

  -- The person's own legs in the copied activities, and the accounts they sit in.
  insert into pg_temp.deletion_unit_ids
  select distinct 'record', m.record_id from public.financial_activity_memberships m
   where m.activity_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'activity')
     and m.user_id = p_user_id and m.record_owner_id = p_user_id
  on conflict do nothing;
  insert into pg_temp.deletion_unit_ids
  select distinct 'account', r.account_id from public.financial_records r
   where r.id in (select old_id from pg_temp.deletion_unit_ids where kind = 'record')
  on conflict do nothing;

  -- Activities and records move in place: they keep their ids, revisions
  -- and timestamps, because other people's legs and links name them by id.
  -- Accounts are copied (new ids), since an account also holds rows that go
  -- with the person. An id map per placeholder covers the account copies for
  -- the whole transaction, so units of one scope share one copy.
  insert into pg_temp.deletion_id_map
  select distinct p_placeholder_id, old_id, gen_random_uuid() from pg_temp.deletion_unit_ids
   where kind = 'account'
  on conflict do nothing;
  insert into pg_temp.deletion_fresh_ids
  select u.kind, u.old_id from pg_temp.deletion_unit_ids u
   where u.kind = 'account' and not exists (
     select 1 from pg_temp.deletion_copied c
      where c.placeholder_id = p_placeholder_id and c.kind = u.kind and c.old_id = u.old_id);
  insert into pg_temp.deletion_copied select p_placeholder_id, kind, old_id from pg_temp.deletion_fresh_ids;

  select array_agg(old_id order by old_id), array_agg(new_id order by old_id)
    into v_from, v_to
    from (
      select old_id, new_id from pg_temp.deletion_id_map where placeholder_id = p_placeholder_id
      union all select p_user_id, p_placeholder_id
    ) ids;

  insert into public.financial_accounts
      (id, user_id, space_id, type, currency, nickname, archived, ownership_share_bps, version, created_at, updated_at)
  select m.new_id, p_placeholder_id, a.space_id, a.type, a.currency, null, a.archived,
         a.ownership_share_bps, 1, a.created_at, now()
    from public.financial_accounts a
    join pg_temp.deletion_id_map m on m.placeholder_id = p_placeholder_id and m.old_id = a.id
    join pg_temp.deletion_fresh_ids f on f.kind = 'account' and f.old_id = a.id;

  -- The person's own receipts and import coverage on the moving rows go with
  -- them (their keys are not deferrable and name the person).
  delete from public.financial_activity_receipts
   where user_id = p_user_id
     and activity_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'activity');
  delete from public.financial_operation_receipts
   where user_id = p_user_id
     and record_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'record');
  delete from public.financial_observation_coverage
   where user_id = p_user_id
     and (activity_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'record')
          or observation_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'record'));

  update public.financial_activity_groups
     set user_id = p_placeholder_id
   where id in (select old_id from pg_temp.deletion_unit_ids where kind = 'activity')
     and user_id = p_user_id;
  update public.financial_activity_revisions
     set user_id = p_placeholder_id
   where activity_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'activity')
     and user_id = p_user_id;
  update public.financial_records r
     set user_id = p_placeholder_id, account_id = m.new_id
    from pg_temp.deletion_id_map m
   where r.id in (select old_id from pg_temp.deletion_unit_ids where kind = 'record')
     and r.user_id = p_user_id
     and m.placeholder_id = p_placeholder_id and m.old_id = r.account_id;
  -- Kept history holds amount, date, category and currency: notes, source ids
  -- and correction reasons are dropped and recorded_by cleared. purchase_* and
  -- reversal_* are generated from details; a link to one of the person's own
  -- activities that did not move with this placeholder is dropped.
  update public.financial_record_revisions rr
     set user_id = p_placeholder_id,
         recorded_by = null,
         reason = null,
         details = argus_private.deletion_rewrite_ids(
           (case when rr.details ? 'reversal_of_activity_id'
                      and coalesce((rr.details ->> 'reversal_of_owner_id')::uuid, rr.user_id) = p_user_id
                      and not exists (select 1 from public.financial_activity_groups g
                                       where g.id = (rr.details ->> 'reversal_of_activity_id')::uuid
                                         and g.user_id = p_placeholder_id)
                 then rr.details - 'reversal_of_activity_id' - 'reversal_of_revision' - 'reversal_of_owner_id'
                 else rr.details end)
           - (case when rr.details ? 'purchase_activity_id'
                        and not exists (select 1 from public.financial_activity_groups g
                                         where g.id = (rr.details ->> 'purchase_activity_id')::uuid
                                           and g.user_id = p_placeholder_id)
                   then array['purchase_activity_id', 'purchase_revision'] else array[]::text[] end)
           - 'note' - 'source_id',
           v_from, v_to)
   where rr.record_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'record')
     and rr.user_id = p_user_id;
  update public.financial_activity_memberships
     set user_id = p_placeholder_id
   where activity_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'activity')
     and user_id = p_user_id;
  update public.financial_activity_memberships
     set record_owner_id = p_placeholder_id
   where record_id in (select old_id from pg_temp.deletion_unit_ids where kind = 'record')
     and record_owner_id = p_user_id;

  v_used := exists (select 1 from pg_temp.deletion_unit_ids);

  if p_unit_kind = 'plan' then
    -- Claims, archives and allocation history of this plan point at the copies.
    update public.financial_plan_links l
       set activity_owner_id = g.user_id
      from public.financial_activity_groups g
     where l.binding_id = p_unit_id and l.activity_owner_id = p_user_id
       and g.id = l.activity_id and g.user_id <> p_user_id;
    -- Every claim's accepted legs name accounts; the person's now have copies.
    update public.financial_plan_links l
       set attribution = argus_private.deletion_rewrite_ids(l.attribution, v_from, v_to)
     where l.binding_id = p_unit_id and l.attribution is not null;
    update public.household_plan_archived_claims c
       set activity_owner_id = g.user_id
      from public.financial_activity_groups g
     where c.binding_id = p_unit_id and c.activity_owner_id = p_user_id
       and g.id = c.activity_id and g.user_id <> p_user_id;
    update public.household_plan_archived_activities c
       set activity_owner_id = g.user_id
      from public.financial_activity_groups g
     where c.binding_id = p_unit_id and c.activity_owner_id = p_user_id
       and g.id = c.activity_id and g.user_id <> p_user_id;
    update public.financial_goal_allocation_revisions r
       set account_id = m.new_id, account_owner_id = p_placeholder_id
      from pg_temp.deletion_id_map m
     where m.placeholder_id = p_placeholder_id and r.binding_id = p_unit_id and r.account_owner_id = p_user_id and r.account_id = m.old_id;
    -- Live backing from the person's accounts ends; the archive keeps it.
    delete from public.financial_goal_allocations
     where binding_id = p_unit_id and account_owner_id = p_user_id;

    -- The household's one Exmiembro membership for this person, shared by
    -- every plan of theirs in the household. former_member_number orders the
    -- household's former members; plan reads number them per plan.
    select * into v_member from public.household_members
     where household_id = v_binding.household_id and user_id = p_user_id
     order by joined_at desc, id desc limit 1;
    if found then
      select id into v_placeholder_mid from public.household_members
       where household_id = v_binding.household_id and user_id = p_placeholder_id;
      if v_placeholder_mid is null then
        select coalesce(max(former_member_number), 0) + 1 into v_number
          from public.household_members
         where household_id = v_binding.household_id and former_member_number is not null;
        v_placeholder_mid := gen_random_uuid();
        insert into public.household_members
            (id, household_id, user_id, joined_at, left_at, display_name, former_member_number)
        values (v_placeholder_mid, v_binding.household_id, p_placeholder_id, v_member.joined_at,
                coalesce(v_member.left_at, now()), 'Exmiembro', v_number);
      end if;
      select * into v_participant from public.household_plan_participants
       where binding_id = p_unit_id
         and membership_id in (select id from public.household_members
                                where household_id = v_binding.household_id and user_id = p_user_id)
       order by joined_at limit 1;
      insert into public.household_plan_participants
          (binding_id, household_id, membership_id, permission, revoked_at, granted_revision, joined_at)
      values (p_unit_id, v_binding.household_id, v_placeholder_mid,
              coalesce(v_participant.permission, 'view'),
              coalesce(v_participant.revoked_at, now()),
              coalesce(v_participant.granted_revision, v_binding.first_shared_revision),
              coalesce(v_participant.joined_at, v_member.joined_at));
      delete from public.household_plan_participants
       where binding_id = p_unit_id
         and membership_id in (select id from public.household_members
                                where household_id = v_binding.household_id and user_id = p_user_id);
      update public.financial_plan_links
         set contributor_membership_id = v_placeholder_mid
       where binding_id = p_unit_id
         and contributor_membership_id in (select id from public.household_members where user_id = p_user_id);
      update public.financial_goal_allocations
         set contributor_membership_id = v_placeholder_mid
       where binding_id = p_unit_id
         and contributor_membership_id in (select id from public.household_members where user_id = p_user_id);
      update public.financial_goal_allocation_revisions
         set contributor_membership_id = v_placeholder_mid
       where binding_id = p_unit_id
         and contributor_membership_id in (select id from public.household_members where user_id = p_user_id);
      update public.financial_plan_responsibilities r
         set membership_id = v_placeholder_mid
       where r.kind = v_binding.kind and r.definition_id = v_binding.definition_id
         and r.owner_id = v_binding.owner_user_id
         and r.membership_id in (select id from public.household_members where user_id = p_user_id);
      delete from public.household_plan_receipts
       where binding_id = p_unit_id
         and (actor_id = p_user_id
              or membership_id in (select id from public.household_members where user_id = p_user_id));
      v_used := true;

      -- A read-only archive the person still owns (shared debt plans, Lucas,
      -- Oct 2) moves to this placeholder together with its debt account.
      if v_binding.owner_user_id = p_user_id then
        if v_binding.kind = 'debt' then
          select m.new_id into v_debt_copy
            from public.financial_debt_plans d
            join pg_temp.deletion_id_map m
              on m.placeholder_id = p_placeholder_id and m.old_id = d.debt_account_id
           where d.id = v_binding.definition_id and d.user_id = p_user_id;
        end if;
        perform argus_private.deletion_rekey_binding(
          p_unit_id, p_user_id, p_placeholder_id, v_placeholder_mid, v_debt_copy
        );
      end if;
    end if;
  end if;

  set constraints all immediate;
  return v_used;
end;
$$;

revoke all on function argus_private.deletion_place_unit(uuid, text, uuid, uuid)
  from public, anon, authenticated;

-- Steps 5.1 (what is left), 5.3, 6 and the clears outside the FKs. Ends with
-- every constraint immediate and fails if anything would still block, or
-- still hold the person's id, once the Admin API deletes the auth user.
create function argus_private.deletion_finish(p_user_id uuid, p_actor_hash text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_email text;
  v_threads text[];
  v_blocker text;
begin
  perform argus_private.require_deletion_writer();
  perform argus_private.defer_deletion_keys();
  select email into v_email from auth.users where id = p_user_id;

  -- 5.1: the person's command receipts and their name on others' revisions.
  delete from public.household_plan_receipts
   where actor_id = p_user_id
      or membership_id in (select id from public.household_members where user_id = p_user_id);
  update public.financial_plan_definition_revisions set actor_id = null where actor_id = p_user_id;
  delete from public.household_account_grants
   where owner_user_id = p_user_id
      or recipient_membership_id in (select id from public.household_members where user_id = p_user_id);
  delete from public.household_command_receipts where actor_id = p_user_id;

  -- 5.3: the person's own remaining plans, explicitly.
  delete from public.financial_plan_links where user_id = p_user_id;
  delete from public.financial_goal_allocations where goal_owner_id = p_user_id or account_owner_id = p_user_id;
  delete from public.financial_plan_responsibilities where owner_id = p_user_id;
  delete from public.financial_budgets where user_id = p_user_id;
  delete from public.financial_expectations where user_id = p_user_id;
  delete from public.financial_goals where user_id = p_user_id;
  delete from public.financial_debt_plans where user_id = p_user_id;
  delete from public.financial_goal_allocation_revisions where goal_owner_id = p_user_id;
  delete from public.financial_plan_definition_revisions where owner_id = p_user_id;

  -- 6: feedback keeps no email or user id.
  update public.feedback
     set context = context - 'account_email' - 'user_id' - 'email'
   where (user_id = p_user_id or (v_email is not null and context ->> 'account_email' = v_email))
     and context is not null;

  -- Outside the FKs (Marcus's design note, section 3).
  select array_agg(id::text) into v_threads from public.conversations where user_id = p_user_id;
  if v_threads is not null then
    delete from public.checkpoint_writes where thread_id = any(v_threads);
    delete from public.checkpoint_blobs where thread_id = any(v_threads);
    delete from public.checkpoints where thread_id = any(v_threads);
  end if;
  delete from public.argus_memory_vectors where payload ->> 'user_id' = p_user_id::text;
  if v_email is not null then
    delete from public.private_alpha_allowlist where lower(email) = lower(v_email);
    delete from public.private_alpha_access_welcome_claims where lower(recipient_email) = lower(v_email);
    delete from public.private_alpha_access_welcome_deliveries where lower(recipient_email) = lower(v_email);
  end if;
  delete from public.visitor_usage_counters
   where visitor_key in ('user:' || p_user_id::text, 'session:' || p_user_id::text);
  if p_actor_hash is not null then
    delete from public.guest_funnel_milestones where subject_key = p_actor_hash;
  end if;

  set constraints all immediate;

  -- Nothing that would block the Admin API delete, or keep the id, is left.
  v_blocker := case
    when exists (select 1 from public.financial_plan_definition_revisions where owner_id = p_user_id or actor_id = p_user_id)
      then 'financial_plan_definition_revisions'
    when exists (select 1 from public.household_plan_receipts where actor_id = p_user_id)
      then 'household_plan_receipts'
    when exists (select 1 from public.households where admin_user_id = p_user_id and status = 'active')
      then 'households.admin_user_id'
    when exists (select 1 from public.household_plan_bindings where owner_user_id = p_user_id)
      then 'household_plan_bindings'
    when exists (select 1 from public.household_plan_participants p join public.household_members m on m.id = p.membership_id where m.user_id = p_user_id)
      then 'household_plan_participants'
    when exists (select 1 from public.financial_plan_responsibilities r join public.household_members m on m.id = r.membership_id where m.user_id = p_user_id)
      then 'financial_plan_responsibilities'
    when exists (select 1 from public.financial_plan_links l join public.household_members m on m.id = l.contributor_membership_id where m.user_id = p_user_id)
      then 'financial_plan_links.contributor_membership_id'
    when exists (select 1 from public.financial_goal_allocation_revisions r join public.household_members m on m.id = r.contributor_membership_id where m.user_id = p_user_id)
      then 'financial_goal_allocation_revisions.contributor_membership_id'
    when exists (select 1 from public.financial_plan_links where activity_owner_id = p_user_id)
      then 'financial_plan_links.activity_owner_id'
    when exists (select 1 from public.household_plan_archived_claims where activity_owner_id = p_user_id)
      then 'household_plan_archived_claims'
    when exists (select 1 from public.household_plan_archived_activities where activity_owner_id = p_user_id)
      then 'household_plan_archived_activities'
    when exists (select 1 from public.financial_goal_allocation_revisions where account_owner_id = p_user_id)
      then 'financial_goal_allocation_revisions.account_owner_id'
    when exists (select 1 from public.financial_activity_memberships where record_owner_id = p_user_id and user_id <> p_user_id)
      then 'financial_activity_memberships.record_owner_id'
    when exists (select 1 from public.financial_activity_memberships where user_id = p_user_id and record_owner_id <> p_user_id)
      then 'retain_foreign_activity'
    when exists (select 1 from public.financial_record_revisions where reversal_of_owner_id = p_user_id and user_id <> p_user_id)
      then 'financial_record_revisions.reversal_of_owner_id'
    when exists (select 1 from public.financial_asset_changes where recorded_by = p_user_id and user_id <> p_user_id)
      then 'financial_asset_changes.recorded_by'
    else null end;
  if v_blocker is not null then
    raise exception 'account_deletion_blocker_left: %', v_blocker using errcode = '55000';
  end if;
end;
$$;

revoke all on function argus_private.deletion_finish(uuid, text)
  from public, anon, authenticated;

-- The deletion command runs as the API's server role. Each writer still
-- refuses to run unless argus.locked_history_writer = 'deletion'.
grant execute on function
    argus_private.deletion_hand_over_plans(uuid, uuid),
    argus_private.deletion_pass_on_archives(uuid),
    argus_private.deletion_place_unit(uuid, text, uuid, uuid),
    argus_private.deletion_finish(uuid, text)
  to service_role;
