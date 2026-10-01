-- Household membership, invitations, and explicit account grants.
-- Spec: docs/specs/lanes/household-permission-policy.md
-- Founder-approved permission policy 2026-10-01.
--
-- Account ownership stays financial_accounts.user_id. Grants never rewrite
-- ownership or space_id. Clients hold no insert/update; the API pool writes.

create table if not exists public.households (
    id uuid primary key default gen_random_uuid(),
    name text check (name is null or char_length(name) between 1 and 80),
    status text not null default 'active' check (status in ('active', 'closed')),
    created_by uuid not null references auth.users(id) on delete restrict,
    admin_user_id uuid not null references auth.users(id) on delete restrict,
    created_at timestamptz not null default now(),
    closed_at timestamptz,
    check (
        (status = 'active' and closed_at is null)
        or (status = 'closed' and closed_at is not null)
    )
);

create index if not exists households_admin_idx
    on public.households (admin_user_id)
    where status = 'active';

create table if not exists public.household_members (
    id uuid primary key default gen_random_uuid(),
    household_id uuid not null references public.households(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    joined_at timestamptz not null default now(),
    left_at timestamptz,
    unique (id, household_id, user_id)
);

create unique index if not exists household_members_one_active_idx
    on public.household_members (household_id, user_id)
    where left_at is null;

create index if not exists household_members_user_active_idx
    on public.household_members (user_id)
    where left_at is null;

create table if not exists public.household_invitations (
    id uuid primary key default gen_random_uuid(),
    household_id uuid not null references public.households(id) on delete cascade,
    token_hash text not null unique,
    created_by uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    revoked_at timestamptz,
    accepted_by uuid references auth.users(id) on delete set null,
    accepted_at timestamptz,
    check (expires_at > created_at),
    check (
        (accepted_by is null and accepted_at is null)
        or (accepted_by is not null and accepted_at is not null)
    )
);

create index if not exists household_invitations_household_idx
    on public.household_invitations (household_id, created_at desc);

create table if not exists public.household_account_grants (
    id uuid primary key default gen_random_uuid(),
    household_id uuid not null references public.households(id) on delete cascade,
    account_id uuid not null,
    owner_user_id uuid not null,
    permission text not null default 'view' check (permission in ('view', 'edit')),
    created_at timestamptz not null default now(),
    revoked_at timestamptz,
    foreign key (account_id, owner_user_id)
        references public.financial_accounts (id, user_id) on delete cascade
);

create unique index if not exists household_account_grants_one_active_idx
    on public.household_account_grants (household_id, account_id)
    where revoked_at is null;

create index if not exists household_account_grants_household_idx
    on public.household_account_grants (household_id)
    where revoked_at is null;

alter table public.households enable row level security;
alter table public.household_members enable row level security;
alter table public.household_invitations enable row level security;
alter table public.household_account_grants enable row level security;

-- Members may read their active household and fellow active members.
drop policy if exists households_member_select on public.households;
create policy households_member_select on public.households
    for select to authenticated
    using (
        exists (
            select 1 from public.household_members m
            where m.household_id = households.id
              and m.user_id = (select auth.uid())
              and m.left_at is null
        )
    );

drop policy if exists household_members_peer_select on public.household_members;
create policy household_members_peer_select on public.household_members
    for select to authenticated
    using (
        exists (
            select 1 from public.household_members self
            where self.household_id = household_members.household_id
              and self.user_id = (select auth.uid())
              and self.left_at is null
        )
        and left_at is null
    );

drop policy if exists household_invitations_admin_select on public.household_invitations;
create policy household_invitations_admin_select on public.household_invitations
    for select to authenticated
    using (
        exists (
            select 1 from public.households h
            where h.id = household_invitations.household_id
              and h.admin_user_id = (select auth.uid())
              and h.status = 'active'
        )
    );

drop policy if exists household_account_grants_member_select on public.household_account_grants;
create policy household_account_grants_member_select on public.household_account_grants
    for select to authenticated
    using (
        revoked_at is null
        and exists (
            select 1 from public.household_members m
            where m.household_id = household_account_grants.household_id
              and m.user_id = (select auth.uid())
              and m.left_at is null
        )
    );

revoke all on public.households from anon, authenticated;
revoke all on public.household_members from anon, authenticated;
revoke all on public.household_invitations from anon, authenticated;
revoke all on public.household_account_grants from anon, authenticated;

grant select on public.households to authenticated;
grant select on public.household_members to authenticated;
grant select on public.household_invitations to authenticated;
grant select on public.household_account_grants to authenticated;
