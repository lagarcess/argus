-- Ordered between the registry preview and landed selected-turn migration.
-- Preserve preview deletion revocation while freeing the canonical trigger name.
-- Fresh databases have no preview trigger because the unlanded declaration was
-- removed; already-applied previews retain it until this identity-checked bridge.
do $$
declare
  v_trigger oid;
  v_compat oid;
  v_old oid := to_regprocedure('public.revoke_public_excerpts_for_deleted_message()');
  v_shared oid := to_regprocedure('public.revoke_public_excerpts_for_deleted_source()');
begin
  select tgfoid into v_trigger from pg_trigger
   where tgrelid = 'public.messages'::regclass
     and tgname = 'revoke_public_excerpts_on_message_delete' and not tgisinternal;
  select tgfoid into v_compat from pg_trigger
   where tgrelid = 'public.messages'::regclass
     and tgname = 'revoke_public_excerpts_on_message_delete_registry_compat'
     and not tgisinternal;
  if v_compat is not null and (v_old is null or v_compat <> v_old) then
    raise exception 'unexpected public excerpt compatibility trigger function';
  end if;
  if v_trigger is null or (v_shared is not null and v_trigger = v_shared) then
    return;
  end if;
  if v_old is null or v_trigger <> v_old or v_compat is not null then
    raise exception 'unexpected public excerpt message trigger function';
  end if;
  alter trigger revoke_public_excerpts_on_message_delete on public.messages
    rename to revoke_public_excerpts_on_message_delete_registry_compat;
end;
$$;
