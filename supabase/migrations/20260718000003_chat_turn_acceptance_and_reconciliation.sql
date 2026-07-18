-- #240: two database-owned boundaries for the ordinary chat-turn lifecycle.
--
-- accept_chat_turn: the accepted user message persists through the canonical
-- serialized append boundary (append_conversation_message owns ownership,
-- message identity + replay, messages.user_id, monotonic created_at, the
-- preview, and conversation updated_at) and the lifecycle row lands in the
-- same transaction, so a lifecycle failure can never orphan an accepted
-- message and no second messages writer exists.
--
-- reconcile_stale_chat_turns: stale selection on the database clock,
-- at-most-20 deterministic ordering, row locking, post-lock stale recheck,
-- the complete owner/conversation/request/turn/terminal evidence predicate
-- with failure precedence on equal timestamps, and the terminal transition.

create or replace function public.accept_chat_turn(
    p_user_id uuid,
    p_conversation_id uuid,
    p_message_id uuid,
    p_role text,
    p_content text,
    p_metadata jsonb,
    p_created_at timestamptz,
    p_preview text,
    p_request_id text
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_message jsonb;
begin
    select appended.message into v_message
      from public.append_conversation_message(
        p_user_id,
        p_conversation_id,
        p_message_id,
        p_role,
        p_content,
        p_metadata,
        p_created_at,
        p_preview,
        null, null, null, null
      ) as appended;

    if v_message is null then
        raise exception 'chat turn acceptance did not persist the message';
    end if;

    insert into public.chat_turn_lifecycles (
        turn_id, user_id, conversation_id, request_id, status
    ) values (
        (v_message ->> 'id')::uuid, p_user_id, p_conversation_id,
        p_request_id, 'accepted'
    )
    on conflict (turn_id) do nothing;

    return v_message;
end;
$$;

revoke all on function public.accept_chat_turn(
    uuid, uuid, uuid, text, text, jsonb, timestamptz, text, text
) from public, anon, authenticated;
grant execute on function public.accept_chat_turn(
    uuid, uuid, uuid, text, text, jsonb, timestamptz, text, text
) to service_role;

create or replace function public.reconcile_stale_chat_turns(
    p_conversation_id uuid,
    p_user_id uuid
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_now timestamptz := now();
    v_cutoff timestamptz := now() - interval '15 minutes';
    v_row public.chat_turn_lifecycles%rowtype;
    v_stale record;
    v_evidence record;
    v_reconciled jsonb := '[]'::jsonb;
begin
    -- Owner scope: reconciliation acts only for the conversation's owner.
    if not exists (
        select 1 from public.conversations c
        where c.id = p_conversation_id and c.user_id = p_user_id
    ) then
        raise exception 'conversation is not owned by the reconciling user';
    end if;

    for v_stale in
        select turn_id
        from public.chat_turn_lifecycles
        where conversation_id = p_conversation_id
          and user_id = p_user_id
          and status in ('accepted', 'running')
          and coalesce(running_at, accepted_at) <= v_cutoff
        order by coalesce(running_at, accepted_at) asc, turn_id asc
        limit 20
    loop
        -- Row lock, then stale recheck: a turn freshened by a concurrent
        -- running transition after the stale read is spared.
        select * into v_row
        from public.chat_turn_lifecycles
        where turn_id = v_stale.turn_id
        for update;
        if not found
           or v_row.status not in ('accepted', 'running')
           or coalesce(v_row.running_at, v_row.accepted_at) > v_cutoff then
            continue;
        end if;

        -- Complete evidence predicate: the message's own writer, the owner
        -- (via the conversation), the lifecycle conversation, assistant role,
        -- exact turn and request identity, terminal flag, and a terminal
        -- status; candidates order by created_at asc with failure
        -- precedence, then id.
        select m.id, m.metadata->'agent_runtime_turn'->>'status' as turn_status
        into v_evidence
        from public.messages m
        join public.conversations c on c.id = m.conversation_id
        where m.conversation_id = v_row.conversation_id
          and m.user_id = v_row.user_id
          and c.user_id = v_row.user_id
          and m.role = 'assistant'
          and m.metadata->'agent_runtime_turn'->>'turn_id' = v_row.turn_id::text
          and m.metadata->'agent_runtime_turn'->>'request_id' = v_row.request_id
          and (m.metadata->'agent_runtime_turn'->>'terminal')::boolean is true
          and m.metadata->'agent_runtime_turn'->>'status'
              in ('completed', 'succeeded', 'recoverable_failed', 'failed')
        order by
            m.created_at asc,
            case when m.metadata->'agent_runtime_turn'->>'status'
                 in ('recoverable_failed', 'failed') then 0 else 1 end asc,
            m.id asc
        limit 1;

        if found then
            update public.chat_turn_lifecycles
            set status = 'reconciled',
                reconciled_outcome = case
                    when v_evidence.turn_status in ('recoverable_failed', 'failed')
                    then 'recoverable_failed' else 'completed' end,
                assistant_message_id = v_evidence.id,
                finished_at = v_now,
                updated_at = v_now
            where turn_id = v_row.turn_id
            returning * into v_row;
        else
            update public.chat_turn_lifecycles
            set status = 'abandoned',
                failure_code = 'turn_abandoned',
                retryable = true,
                finished_at = v_now,
                updated_at = v_now
            where turn_id = v_row.turn_id
            returning * into v_row;
        end if;
        v_reconciled := v_reconciled || to_jsonb(v_row);
    end loop;

    return jsonb_build_object('reconciled', v_reconciled);
end;
$$;

revoke all on function public.reconcile_stale_chat_turns(uuid, uuid)
    from public, anon, authenticated;
grant execute on function public.reconcile_stale_chat_turns(uuid, uuid)
    to service_role;
