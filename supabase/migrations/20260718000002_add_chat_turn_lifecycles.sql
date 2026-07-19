-- #240: durable ordinary chat-turn lifecycle. One current row per accepted
-- non-backtest chat turn; recovery truth, not a second queue or chat brain.

create table if not exists public.chat_turn_lifecycles (
    turn_id uuid primary key references public.messages(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    conversation_id uuid not null references public.conversations(id) on delete cascade,
    request_id text not null,
    status text not null default 'accepted' check (
        status in (
            'accepted', 'running', 'completed', 'recoverable_failed',
            'abandoned', 'reconciled'
        )
    ),
    accepted_at timestamptz not null default now(),
    running_at timestamptz,
    terminal_at timestamptz,
    reconciled_at timestamptz,
    assistant_message_id uuid references public.messages(id) on delete set null,
    reconciled_outcome text check (
        reconciled_outcome in ('completed', 'recoverable_failed')
    ),
    failure_code text,
    retryable boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    -- reconciled_outcome exists exactly when the row is reconciled.
    constraint chat_turn_lifecycles_reconciled_outcome_matches check (
        (status = 'reconciled') = (reconciled_outcome is not null)
    ),
    -- abandoned means no qualifying terminal assistant message settled it.
    constraint chat_turn_lifecycles_abandoned_unlinked check (
        status <> 'abandoned' or assistant_message_id is null
    )
);

-- One terminal assistant message cannot settle two turns.
create unique index if not exists idx_chat_turn_lifecycles_assistant_unique
    on public.chat_turn_lifecycles (assistant_message_id)
    where assistant_message_id is not null;

create index if not exists idx_chat_turn_lifecycles_conversation_stale
    on public.chat_turn_lifecycles (
        conversation_id, coalesce(running_at, accepted_at) asc, turn_id asc
    )
    where status in ('accepted', 'running');

alter table public.chat_turn_lifecycles enable row level security;

-- Owners may read their lifecycle truth; every write goes through the
-- service-role compare-and-set function below.
drop policy if exists chat_turn_lifecycles_select_own on public.chat_turn_lifecycles;
create policy chat_turn_lifecycles_select_own
    on public.chat_turn_lifecycles for select
    using (auth.uid() = user_id);

revoke insert, update, delete on public.chat_turn_lifecycles
    from public, anon, authenticated;

create or replace function public.transition_chat_turn_lifecycle(
    p_turn_id uuid,
    p_to_status text,
    p_assistant_message_id uuid default null,
    p_reconciled_outcome text default null,
    p_failure_code text default null,
    p_retryable boolean default null
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_row public.chat_turn_lifecycles%rowtype;
    v_now timestamptz := now();
    v_allowed boolean;
begin
    if p_to_status = 'reconciled'
       and coalesce(p_reconciled_outcome, '')
           not in ('completed', 'recoverable_failed') then
        return jsonb_build_object('outcome', 'invalid');
    end if;
    if p_to_status <> 'reconciled' and p_reconciled_outcome is not null then
        return jsonb_build_object('outcome', 'invalid');
    end if;

    select * into v_row
    from public.chat_turn_lifecycles
    where turn_id = p_turn_id
    for update;
    if not found then
        return jsonb_build_object('outcome', 'missing');
    end if;

    if v_row.status = p_to_status
       or v_row.status in (
           'completed', 'recoverable_failed', 'abandoned', 'reconciled'
       ) then
        -- No-op requires the complete effective truth: target status,
        -- assistant link, reconciliation outcome, exact (null-safe)
        -- failure_code, and effective retryable (omitted means false, the
        -- column default). Omitted values are never wildcards — a replay
        -- that drops or changes stored failure evidence conflicts.
        if v_row.status = p_to_status
           and coalesce(v_row.assistant_message_id::text, '')
               = coalesce(p_assistant_message_id::text, '')
           and coalesce(v_row.reconciled_outcome, '')
               = coalesce(p_reconciled_outcome, '')
           and p_failure_code is not distinct from v_row.failure_code
           and coalesce(p_retryable, false) = coalesce(v_row.retryable, false)
        then
            return jsonb_build_object('outcome', 'noop', 'row', to_jsonb(v_row));
        end if;
        return jsonb_build_object('outcome', 'conflict', 'row', to_jsonb(v_row));
    end if;

    v_allowed := case p_to_status
        when 'running' then v_row.status = 'accepted'
        when 'completed' then v_row.status in ('accepted', 'running')
        when 'recoverable_failed' then v_row.status in ('accepted', 'running')
        when 'abandoned' then v_row.status in ('accepted', 'running')
        when 'reconciled' then v_row.status in ('accepted', 'running')
        else false
    end;
    if not v_allowed then
        return jsonb_build_object('outcome', 'conflict', 'row', to_jsonb(v_row));
    end if;

    update public.chat_turn_lifecycles
    set status = p_to_status,
        running_at = case when p_to_status = 'running' then v_now else running_at end,
        terminal_at = case
            when p_to_status <> 'running' then v_now else terminal_at end,
        reconciled_at = case
            when p_to_status = 'reconciled' then v_now else reconciled_at end,
        assistant_message_id =
            coalesce(p_assistant_message_id, assistant_message_id),
        reconciled_outcome = case
            when p_to_status = 'reconciled' then p_reconciled_outcome
            else reconciled_outcome end,
        failure_code = coalesce(p_failure_code, failure_code),
        retryable = coalesce(p_retryable, retryable),
        updated_at = v_now
    where turn_id = p_turn_id
    returning * into v_row;

    return jsonb_build_object('outcome', 'applied', 'row', to_jsonb(v_row));
end;
$$;

revoke all on function public.transition_chat_turn_lifecycle(
    uuid, text, uuid, text, text, boolean
) from public, anon, authenticated;
grant execute on function public.transition_chat_turn_lifecycle(
    uuid, text, uuid, text, text, boolean
) to service_role;
