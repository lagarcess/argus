-- In-place artifact updates join the serialized conversation writer.
-- append_conversation_message declared that clients must not bypass the
-- serialized writer; this function gives the non-turn rewrite the same
-- spine: the owned conversation row is locked for the transaction, the
-- write is conditional on the exact metadata the caller read (an empty
-- result is the conflict signal, never a silent last-writer win), and the
-- conversation's denormalized preview follows the rewritten card when that
-- card is the latest message. updated_at is untouched: a non-turn change
-- spends nothing and must not reorder recents.

create or replace function public.update_conversation_message_artifact(
  p_user_id uuid,
  p_conversation_id uuid,
  p_message_id uuid,
  p_content text,
  p_metadata jsonb,
  p_expected_source_metadata jsonb,
  p_preview text
)
returns table (
  message jsonb
)
language plpgsql
security invoker
set search_path = public
as $$
declare
  v_conversation_id uuid;
  v_message public.messages%rowtype;
  v_latest_id uuid;
begin
  select c.id
    into v_conversation_id
    from public.conversations as c
   where c.id = p_conversation_id
     and c.user_id = p_user_id
   for update;

  if not found then
    raise exception 'Conversation not found or not owned by user.'
      using errcode = 'P0002';
  end if;

  select m.*
    into v_message
    from public.messages as m
   where m.id = p_message_id
     and m.user_id = p_user_id
     and m.conversation_id = p_conversation_id;

  if not found then
    raise exception 'Message not found or not owned by user.'
      using errcode = 'P0002';
  end if;

  if p_expected_source_metadata is not null
    and v_message.metadata is distinct from p_expected_source_metadata then
    return;
  end if;

  update public.messages as m
     set content = p_content,
         metadata = coalesce(p_metadata, '{}'::jsonb)
   where m.id = p_message_id
  returning * into v_message;

  if nullif(btrim(p_preview), '') is not null then
    select m.id
      into v_latest_id
      from public.messages as m
     where m.user_id = p_user_id
       and m.conversation_id = p_conversation_id
     order by m.created_at desc, m.id desc
     limit 1;

    if v_latest_id = p_message_id then
      update public.conversations as c
         set last_message_preview = p_preview
       where c.id = p_conversation_id
         and c.user_id = p_user_id;
    end if;
  end if;

  return query select to_jsonb(v_message);
end;
$$;

revoke all on function public.update_conversation_message_artifact(
  uuid, uuid, uuid, text, jsonb, jsonb, text
) from public;
revoke all on function public.update_conversation_message_artifact(
  uuid, uuid, uuid, text, jsonb, jsonb, text
) from anon;
revoke all on function public.update_conversation_message_artifact(
  uuid, uuid, uuid, text, jsonb, jsonb, text
) from authenticated;
grant execute on function public.update_conversation_message_artifact(
  uuid, uuid, uuid, text, jsonb, jsonb, text
) to service_role;
