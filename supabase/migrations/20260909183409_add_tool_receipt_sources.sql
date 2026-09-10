-- Message-owned tool answers use the existing frozen receipt store. No run,
-- evidence artifact, or idea is manufactured for a local computation.
alter table public.public_excerpt_snapshots
  add column source_message_id uuid references public.messages(id) on delete set null,
  add column source_artifact_id uuid,
  add column source_input_revision integer check (source_input_revision >= 0),
  add constraint public_excerpt_tool_source_pair check (
    (source_artifact_id is null) = (source_input_revision is null)
  );

create unique index idx_public_excerpt_snapshots_live_tool_result
  on public.public_excerpt_snapshots
    (owner_id, source_message_id, source_artifact_id, source_input_revision)
  where revoked_at is null and source_message_id is not null;

-- The conversation lock is the same deletion boundary used by v1. A message
-- lock then proves that the selected card revision is still the one on record.
-- In-place recompute takes the locks in the same order through its existing CAS.
create or replace function public.enforce_public_excerpt_source_is_live()
returns trigger language plpgsql security definer set search_path = '' as $$
declare
  v_deleted_at timestamptz;
  v_metadata jsonb;
begin
  if new.source_conversation_id is null then
    if new.source_message_id is not null then
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

  if new.source_message_id is not null then
    if new.evidence_artifact_id is not null or new.source_run_id is not null
       or new.source_artifact_id is null or new.source_input_revision is null then
      raise exception 'public_excerpt_source_missing' using errcode = '23514';
    end if;
    select metadata into v_metadata from public.messages
     where id = new.source_message_id and user_id = new.owner_id
       and conversation_id = new.source_conversation_id and role = 'assistant'
     for share;
    if not found then
      raise exception 'public_excerpt_source_missing' using errcode = '23514';
    end if;
    if not exists (
      select 1 from jsonb_array_elements(
        case when jsonb_typeof(v_metadata->'tool_result_cards') = 'array'
          then v_metadata->'tool_result_cards' else '[]'::jsonb end
      ) as card
      where card->>'kind' = 'tool_result'
        and card->>'artifact_id' = new.source_artifact_id::text
        and card->'input_revision' = to_jsonb(new.source_input_revision)
        and card->'outcome'->>'status' = 'succeeded'
    ) then
      raise exception 'public_excerpt_source_changed' using errcode = '23514';
    end if;
  elsif new.source_artifact_id is not null then
    raise exception 'public_excerpt_source_missing' using errcode = '23514';
  end if;
  return new;
end;
$$;

-- Card identity/revision never changes. FK cleanup may clear a deleted source
-- message only after the receipt was revoked by that deletion.
create function public.prevent_public_excerpt_tool_source_update()
returns trigger language plpgsql security invoker set search_path = '' as $$
begin
  if new.source_artifact_id is distinct from old.source_artifact_id
     or new.source_input_revision is distinct from old.source_input_revision
     or (new.source_message_id is distinct from old.source_message_id and not (
       new.source_message_id is null and new.revoked_at is not null
       and not exists (select 1 from public.messages where id = old.source_message_id)
     )) then
    raise exception 'public_excerpt_snapshots immutable tool source'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger prevent_public_excerpt_tool_source_update
before update on public.public_excerpt_snapshots
for each row execute function public.prevent_public_excerpt_tool_source_update();

create function public.revoke_public_excerpts_for_deleted_message()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  update public.public_excerpt_snapshots as snapshot
     set revoked_at = now(), revocation_reason = 'source_deleted'
   where snapshot.source_message_id = old.id and snapshot.revoked_at is null
     and exists (select 1 from public.profiles where id = snapshot.owner_id);
  return old;
end;
$$;

revoke all on function public.enforce_public_excerpt_source_is_live()
  from public, anon, authenticated;
revoke all on function public.prevent_public_excerpt_tool_source_update()
  from public, anon, authenticated;
revoke all on function public.revoke_public_excerpts_for_deleted_message()
  from public, anon, authenticated;
