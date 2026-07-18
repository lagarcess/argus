-- #230: database-owned atomic backtest admission and idempotency.
-- Adds the approved reservation identity columns and one admission function
-- that resolves, in this exact order: exact replay or identity collision
-- first, unique-simulation allowance second, per-user capacity third, global
-- capacity fourth; only then inserts the job and charges the allowance in the
-- same transaction. A count-then-insert sequence in the API is not conforming
-- admission.

alter table public.backtest_jobs
    add column if not exists operation_scope text not null
        default 'chat.run_backtest'
        check (operation_scope in ('chat.run_backtest', 'backtests.run')),
    add column if not exists identity_hash text;

-- Approved direct-run disposition: a backtests.run job may have no
-- conversation; ownership remains user_id.
alter table public.backtest_jobs
    alter column conversation_id drop not null;

-- The unique reservation boundary is (user_id, operation_scope, idempotency_key).
drop index if exists idx_backtest_jobs_user_idempotency_key;
create unique index if not exists backtest_jobs_reservation_idx
    on public.backtest_jobs (user_id, operation_scope, idempotency_key)
    where idempotency_key is not null;

create index if not exists backtest_jobs_status_started_idx
    on public.backtest_jobs (status, started_at asc, id asc);

create or replace function public.admit_backtest_job(
    p_user_id uuid,
    p_operation_scope text,
    p_idempotency_key text,
    p_identity_hash text,
    p_payload_hash text,
    p_launch_payload jsonb,
    p_initial_status text,
    p_conversation_id uuid default null,
    p_request_message_id uuid default null,
    p_confirmation_message_id uuid default null,
    p_execution_metadata jsonb default '{}'::jsonb,
    p_user_running_limit integer default 1,
    p_user_queued_limit integer default 2,
    p_global_running_limit integer default 5,
    p_global_queued_limit integer default 10,
    p_simulation_day_limit integer default 50
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_existing public.backtest_jobs%rowtype;
    v_job public.backtest_jobs%rowtype;
    v_now timestamptz := now();
    v_stale record;
    v_user_running integer;
    v_user_queued integer;
    v_global_running integer;
    v_global_queued integer;
    v_charged integer;
begin
    if p_operation_scope not in ('chat.run_backtest', 'backtests.run') then
        raise exception 'unsupported operation scope %', p_operation_scope;
    end if;
    if p_initial_status not in ('queued', 'running') then
        raise exception 'unsupported initial status %', p_initial_status;
    end if;

    -- Serialize admissions on one advisory lock so replay/collision, stale
    -- reconciliation, capacity counting, insert, and allowance charge cannot
    -- interleave between transactions.
    perform pg_advisory_xact_lock(hashtext('backtest_admission'));

    -- 1. Exact replay or identity collision, before every other boundary.
    select * into v_existing
    from public.backtest_jobs
    where user_id = p_user_id
      and operation_scope = p_operation_scope
      and idempotency_key = p_idempotency_key
    for update;
    if found then
        if v_existing.identity_hash = p_identity_hash then
            if p_operation_scope = 'backtests.run'
               and v_existing.status = 'running'
               and v_existing.started_at is not null
               and v_existing.started_at <= v_now - interval '15 minutes' then
                update public.backtest_jobs
                set status = 'failed',
                    failure_code = 'direct_execution_abandoned',
                    failure_detail = 'execution_interrupted',
                    retryable = true,
                    finished_at = v_now,
                    updated_at = v_now
                where id = v_existing.id
                returning * into v_existing;
            end if;
            return jsonb_build_object(
                'decision', 'replay',
                'job', to_jsonb(v_existing)
            );
        end if;
        return jsonb_build_object('decision', 'conflict');
    end if;

    -- New-identity direct admissions release capacity stranded by crashed
    -- direct processes: at most 20 stale running direct jobs, oldest first.
    if p_operation_scope = 'backtests.run' then
        for v_stale in
            select id from public.backtest_jobs
            where operation_scope = 'backtests.run'
              and status = 'running'
              and started_at is not null
              and started_at <= v_now - interval '15 minutes'
            order by started_at asc, id asc
            limit 20
            for update
        loop
            update public.backtest_jobs
            set status = 'failed',
                failure_code = 'direct_execution_abandoned',
                failure_detail = 'execution_interrupted',
                retryable = true,
                finished_at = v_now,
                updated_at = v_now
            where id = v_stale.id;
        end loop;
    end if;

    -- 2. Unique-simulation allowance exhaustion.
    if p_simulation_day_limit is not null and p_simulation_day_limit >= 0 then
        select coalesce(sum(used_count), 0) into v_charged
        from public.usage_counters
        where user_id = p_user_id
          and resource = 'backtest_runs'
          and period = 'day'
          and period_start = date_trunc('day', v_now);
        if v_charged >= p_simulation_day_limit then
            return jsonb_build_object('decision', 'allowance_exhausted');
        end if;
    end if;

    -- 3-4. Per-user capacity before global capacity. Direct admissions must
    -- clear the queued and running ceilings at both scopes because they claim
    -- a running slot immediately.
    select
        count(*) filter (where status = 'running' and user_id = p_user_id),
        count(*) filter (where status = 'queued' and user_id = p_user_id),
        count(*) filter (where status = 'running'),
        count(*) filter (where status = 'queued')
    into v_user_running, v_user_queued, v_global_running, v_global_queued
    from public.backtest_jobs
    where status in ('queued', 'running');

    if p_operation_scope = 'backtests.run' or p_initial_status = 'running' then
        if v_user_running >= p_user_running_limit then
            return jsonb_build_object('decision', 'per_user_capacity');
        end if;
    end if;
    if p_operation_scope = 'backtests.run' or p_initial_status = 'queued' then
        if v_user_queued >= p_user_queued_limit then
            return jsonb_build_object('decision', 'per_user_capacity');
        end if;
    end if;
    if p_operation_scope = 'backtests.run' or p_initial_status = 'running' then
        if v_global_running >= p_global_running_limit then
            return jsonb_build_object('decision', 'global_capacity');
        end if;
    end if;
    if p_operation_scope = 'backtests.run' or p_initial_status = 'queued' then
        if v_global_queued >= p_global_queued_limit then
            return jsonb_build_object('decision', 'global_capacity');
        end if;
    end if;

    -- 5. Insert the durable job and charge the allowance together.
    insert into public.backtest_jobs (
        user_id,
        conversation_id,
        request_message_id,
        confirmation_message_id,
        operation_scope,
        idempotency_key,
        identity_hash,
        payload_hash,
        launch_payload,
        status,
        priority,
        attempts,
        max_attempts,
        queued_at,
        started_at,
        execution_metadata
    ) values (
        p_user_id,
        p_conversation_id,
        p_request_message_id,
        p_confirmation_message_id,
        p_operation_scope,
        p_idempotency_key,
        p_identity_hash,
        p_payload_hash,
        p_launch_payload,
        p_initial_status,
        'normal',
        0,
        1,
        v_now,
        case when p_initial_status = 'running' then v_now else null end,
        coalesce(p_execution_metadata, '{}'::jsonb)
    ) returning * into v_job;

    insert into public.usage_counters (
        user_id, resource, period, period_start, period_end, used_count, limit_count
    ) values (
        p_user_id,
        'backtest_runs',
        'day',
        date_trunc('day', v_now),
        date_trunc('day', v_now) + interval '1 day',
        1,
        coalesce(p_simulation_day_limit, 50)
    )
    on conflict (user_id, resource, period, period_start)
    do update set
        used_count = public.usage_counters.used_count + 1,
        updated_at = now();

    return jsonb_build_object(
        'decision', 'admitted',
        'job', to_jsonb(v_job)
    );
end;
$$;

revoke all on function public.admit_backtest_job(
    uuid, text, text, text, text, jsonb, text, uuid, uuid, uuid, jsonb,
    integer, integer, integer, integer, integer
) from public, anon, authenticated;
grant execute on function public.admit_backtest_job(
    uuid, text, text, text, text, jsonb, text, uuid, uuid, uuid, jsonb,
    integer, integer, integer, integer, integer
) to service_role;
