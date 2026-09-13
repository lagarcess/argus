"""Shared reason-to-identity rule for guest handoffs and their SQL validator."""

from __future__ import annotations

from typing import get_args

GUEST_PENDING_ACTION_IDENTITIES = {
    "save_decision": "artifact_id",
    "share_result": "message_id",
}


def render_guest_pending_action_validator() -> str:
    """Derive the frozen migration validator from the owner API contract."""
    from argus.api.schemas import GuestConversionReason, GuestPendingAction

    fields = ", ".join(f"'{field}'" for field in GuestPendingAction.model_fields)
    reasons = ", ".join(f"'{reason}'" for reason in get_args(GuestConversionReason))
    identities = []
    for reason, field in GUEST_PENDING_ACTION_IDENTITIES.items():
        identities.append(f"""  if v_reason = '{reason}' then
    if nullif(p_action ->> '{field}', '') is null then return false; end if;
  elsif p_action ? '{field}' then
    return false;
  end if;""")
    rules = "\n".join(identities)
    return f"""create or replace function argus_private.valid_guest_pending_action(
  p_action jsonb, p_conversation_id uuid
)
returns boolean language plpgsql immutable strict set search_path = '' as $$
declare v_key text; v_reason text;
begin
  if jsonb_typeof(p_action) <> 'object' then return false; end if;
  for v_key in select jsonb_object_keys(p_action) loop
    if v_key not in ({fields}) or jsonb_typeof(p_action -> v_key) <> 'string' then
      return false;
    end if;
  end loop;
  v_reason := p_action ->> 'reason';
  if v_reason is null or v_reason not in ({reasons}) then return false; end if;
  if nullif(p_action ->> 'conversation_id', '') is distinct from p_conversation_id::text
     or nullif(p_action ->> 'action_id', '') is null then return false; end if;
{rules}
  return true;
end;
$$;
revoke all on function argus_private.valid_guest_pending_action(jsonb, uuid) from public, anon, authenticated;
grant execute on function argus_private.valid_guest_pending_action(jsonb, uuid) to service_role;
"""
