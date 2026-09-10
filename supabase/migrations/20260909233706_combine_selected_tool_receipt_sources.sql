-- Extend the same frozen selected-turn receipt store with private tool revisions.
-- Bounds derive from PUBLIC_EXCERPT_MAX_TURNS (4) * MAX_TOOL_CALLS (8).
-- Existing payloads and digests are immutable and are never rewritten here.
alter table public.public_excerpt_snapshots
  add column source_tool_bindings jsonb not null default '[]'::jsonb,
  add constraint public_excerpt_tool_bindings_bounded check (
    case when jsonb_typeof(source_tool_bindings) = 'array'
      then jsonb_array_length(source_tool_bindings) <= 32 else false end
  ),
  drop constraint public_excerpt_snapshots_kind_check,
  add constraint public_excerpt_snapshots_kind_check
    check (kind in ('backtest', 'research_answer', 'tool_result', 'mixed')),
  drop constraint public_excerpt_secondary_sources_bounded,
  add constraint public_excerpt_secondary_sources_bounded check (
    cardinality(source_run_ids) <= 32 and cardinality(source_artifact_ids) <= 32
  );

create or replace function public.enforce_public_excerpt_source_is_live()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  v_deleted_at timestamptz;
  v_id uuid;
  v_binding jsonb;
  v_metadata jsonb;
  v_expected jsonb;
  v_actual jsonb;
  v_message_ids uuid[];
begin
  if new.source_conversation_id is null then
    if new.selection_key is not null or new.source_message_id is not null
       or new.source_artifact_id is not null
       or jsonb_array_length(new.source_tool_bindings) > 0 then
      raise exception 'public_excerpt_source_missing' using errcode = '23514';
    end if;
    return new;
  end if;
  select deleted_at into v_deleted_at from public.conversations
   where id = new.source_conversation_id and user_id = new.owner_id for share;
  if not found then
    raise exception 'public_excerpt_source_missing' using errcode = '23514';
  end if;
  if v_deleted_at is not null then
    raise exception 'public_excerpt_source_deleted' using errcode = '23514';
  end if;
  if jsonb_typeof(new.source_tool_bindings) <> 'array'
     or jsonb_array_length(new.source_tool_bindings) > 32 then
    raise exception 'public_excerpt_source_missing' using errcode = '23514';
  end if;
  if jsonb_array_length(new.source_tool_bindings) > 0 and new.selection_key is null then
    raise exception 'public_excerpt_source_missing' using errcode = '23514';
  end if;
  for v_binding in select value from jsonb_array_elements(new.source_tool_bindings) loop
    if jsonb_typeof(v_binding) <> 'object'
       or v_binding - array['message_id','artifact_id','input_revision'] <> '{}'::jsonb
       or jsonb_typeof(v_binding->'message_id') is distinct from 'string'
       or jsonb_typeof(v_binding->'artifact_id') is distinct from 'string'
       or jsonb_typeof(v_binding->'input_revision') is distinct from 'number'
       or (v_binding->>'input_revision') !~ '^(0|[1-9][0-9]*)$'
       or not ((v_binding->>'message_id')::uuid = any(new.source_message_ids)) then
      raise exception 'public_excerpt_source_missing' using errcode = '23514';
    end if;
    perform (v_binding->>'artifact_id')::uuid;
    perform (v_binding->>'input_revision')::integer;
  end loop;
  if jsonb_array_length(new.source_tool_bindings) <> (
    select count(distinct value->>'artifact_id')
      from jsonb_array_elements(new.source_tool_bindings)
  ) then
    raise exception 'public_excerpt_source_changed' using errcode = '23514';
  end if;
  if cardinality(new.source_message_ids) <> (
    select count(distinct id) from unnest(new.source_message_ids) as id
  ) then
    raise exception 'public_excerpt_source_missing' using errcode = '23514';
  end if;
  -- One deterministic lock order for legacy and selected message sources.
  select array_agg(distinct id order by id) into v_message_ids
    from unnest(new.source_message_ids || array[new.source_message_id]) as id
   where id is not null;
  for v_id in select unnest(v_message_ids) order by 1 loop
    select metadata into v_metadata from public.messages
     where id = v_id and user_id = new.owner_id
       and conversation_id = new.source_conversation_id and role = 'assistant' for share;
    if not found then
      raise exception 'public_excerpt_source_missing' using errcode = '23514';
    end if;
    if v_id = new.source_message_id then
      if new.evidence_artifact_id is not null or new.source_run_id is not null
         or new.source_artifact_id is null or new.source_input_revision is null then
        raise exception 'public_excerpt_source_missing' using errcode = '23514';
      end if;
      if not exists (
        select 1 from jsonb_array_elements(case
          when jsonb_typeof(v_metadata->'tool_result_cards') = 'array'
            then v_metadata->'tool_result_cards' else '[]'::jsonb end) as card
         where card->>'kind' = 'tool_result'
           and card->>'artifact_id' = new.source_artifact_id::text
           and card->'input_revision' = to_jsonb(new.source_input_revision)
           and card->'outcome'->>'status' = 'succeeded'
      ) then
        raise exception 'public_excerpt_source_changed' using errcode = '23514';
      end if;
    end if;
    if v_id = any(new.source_message_ids) then
      select coalesce(jsonb_agg(
        jsonb_build_object('artifact_id', value->'artifact_id', 'input_revision', value->'input_revision')
        order by ordinal), '[]'::jsonb) into v_expected
        from jsonb_array_elements(new.source_tool_bindings) with ordinality as binding(value, ordinal)
       where (value->>'message_id')::uuid = v_id;
      if v_metadata ? 'tool_result_cards' or jsonb_array_length(v_expected) > 0 then
        if jsonb_typeof(v_metadata->'tool_result_cards') is distinct from 'array'
           or jsonb_array_length(v_metadata->'tool_result_cards') not between 1 and 8
           or exists (
             select 1 from jsonb_array_elements(v_metadata->'tool_result_cards') as card
              where card->>'kind' is distinct from 'tool_result'
                 or card->'outcome'->>'status' is distinct from 'succeeded'
                 or jsonb_typeof(card->'presentation'->'answer') is distinct from 'object'
           ) then
          raise exception 'public_excerpt_source_changed' using errcode = '23514';
        end if;
        select jsonb_agg(jsonb_build_object(
          'artifact_id', value->'artifact_id', 'input_revision', value->'input_revision'
        ) order by ordinal) into v_actual
          from jsonb_array_elements(v_metadata->'tool_result_cards') with ordinality as card(value, ordinal);
        if v_actual is distinct from v_expected then
          raise exception 'public_excerpt_source_changed' using errcode = '23514';
        end if;
      end if;
    end if;
  end loop;
  if new.source_message_id is null and new.source_artifact_id is not null then
    raise exception 'public_excerpt_source_missing' using errcode = '23514';
  end if;
  for v_id in select distinct unnest(new.source_run_ids) order by 1 loop
    perform 1 from public.backtest_runs where id = v_id and user_id = new.owner_id
      and conversation_id = new.source_conversation_id and status = 'completed' for share;
    if not found then
      raise exception 'public_excerpt_source_missing' using errcode = '23514';
    end if;
  end loop;
  for v_id in select distinct unnest(new.source_artifact_ids) order by 1 loop
    perform 1 from public.evidence_artifacts where id = v_id and user_id = new.owner_id
      and source_conversation_id = new.source_conversation_id for share;
    if not found then
      raise exception 'public_excerpt_source_missing' using errcode = '23514';
    end if;
  end loop;
  return new;
end;
$$;

create or replace function public.prevent_public_excerpt_tool_source_update()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if new.source_tool_bindings is distinct from old.source_tool_bindings
     or new.source_artifact_id is distinct from old.source_artifact_id
     or new.source_input_revision is distinct from old.source_input_revision
     or (new.source_message_id is distinct from old.source_message_id and not (
       new.source_message_id is null and new.revoked_at is not null
       and not exists (select 1 from public.messages where id = old.source_message_id)
     )) then
    raise exception 'public_excerpt_snapshots immutable tool source' using errcode = '23514';
  end if;
  return new;
end;
$$;

create or replace function public.revoke_public_excerpts_for_deleted_source()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_now timestamptz := now();
begin
  if tg_op = 'DELETE' then
    if tg_table_name = 'conversations' then
      update public.public_excerpt_snapshots as snapshot
         set revoked_at = v_now,
             revocation_reason = 'source_deleted'
       where snapshot.source_conversation_id = old.id
         and snapshot.revoked_at is null
         and exists (
           select 1 from public.profiles as owner
            where owner.id = snapshot.owner_id
         );
    elsif tg_table_name = 'backtest_runs' then
      update public.public_excerpt_snapshots as snapshot
         set revoked_at = v_now,
             revocation_reason = 'source_deleted'
       where (snapshot.source_run_id = old.id or old.id = any(snapshot.source_run_ids))
         and snapshot.revoked_at is null
         and exists (
           select 1 from public.profiles as owner
            where owner.id = snapshot.owner_id
         );
    elsif tg_table_name = 'messages' then
      update public.public_excerpt_snapshots as snapshot
         set revoked_at = v_now, revocation_reason = 'source_deleted'
       where (snapshot.source_message_id = old.id or old.id = any(snapshot.source_message_ids))
         and snapshot.revoked_at is null
         and exists (select 1 from public.profiles as owner where owner.id = snapshot.owner_id);
    else
      update public.public_excerpt_snapshots as snapshot
         set revoked_at = v_now,
             revocation_reason = 'source_deleted'
       where (snapshot.evidence_artifact_id = old.id or old.id = any(snapshot.source_artifact_ids))
         and snapshot.revoked_at is null
         and exists (
           select 1 from public.profiles as owner
            where owner.id = snapshot.owner_id
         );
    end if;
    return old;
  end if;

  if old.deleted_at is null and new.deleted_at is not null then
    update public.public_excerpt_snapshots as snapshot
       set revoked_at = v_now,
           revocation_reason = 'source_deleted'
     where snapshot.source_conversation_id = new.id
       and snapshot.revoked_at is null
       and exists (
         select 1 from public.profiles as owner
          where owner.id = snapshot.owner_id
       );
  end if;
  return new;
end;
$$;

-- Retire only the compatibility trigger this lane owns, after the shared revoker
-- protects both old and new sources. Unexpected identities are never removed.
do $$
declare v_compat oid; v_shared oid;
begin
  select tgfoid into v_shared from pg_trigger
   where tgrelid = 'public.messages'::regclass
     and tgname = 'revoke_public_excerpts_on_message_delete' and not tgisinternal;
  if v_shared is distinct from to_regprocedure('public.revoke_public_excerpts_for_deleted_source()') then
    raise exception 'unexpected public excerpt shared trigger function';
  end if;
  select tgfoid into v_compat from pg_trigger
   where tgrelid = 'public.messages'::regclass
     and tgname = 'revoke_public_excerpts_on_message_delete_registry_compat' and not tgisinternal;
  if v_compat is not null then
    if v_compat is distinct from to_regprocedure('public.revoke_public_excerpts_for_deleted_message()') then
      raise exception 'unexpected public excerpt compatibility trigger function';
    end if;
    drop trigger revoke_public_excerpts_on_message_delete_registry_compat on public.messages;
  end if;
end;
$$;

revoke all on function public.enforce_public_excerpt_source_is_live() from public, anon, authenticated;
revoke all on function public.prevent_public_excerpt_tool_source_update() from public, anon, authenticated;
revoke all on function public.revoke_public_excerpts_for_deleted_source() from public, anon, authenticated;
