from unittest.mock import MagicMock

from argus.domain.supabase_gateway import SupabaseGateway


def _conversation_row(idx: int) -> dict[str, object]:
    return {
        "id": f"conv-{idx}",
        "title": f"Conversation {idx}",
        "title_source": "system_default",
        "language": "en",
        "pinned": False,
        "archived": False,
        "last_message_preview": None,
        "deleted_at": None,
        "created_at": "2026-04-27T00:00:00+00:00",
        "updated_at": "2026-04-27T00:00:00+00:00",
    }


def test_gateway_fetches_all_conversations_in_batches_when_limit_is_none() -> None:
    client = MagicMock()
    gateway = SupabaseGateway(client=client)

    table = client.table.return_value
    select = table.select.return_value
    eq = select.eq.return_value
    eq.is_.return_value = eq
    ordered = eq.order.return_value
    ordered.order.return_value = ordered
    ordered.limit.return_value.execute.return_value.data = []

    def _range_side_effect(start: int, end: int) -> MagicMock:  # noqa: ARG001
        query = MagicMock()
        if start == 0:
            query.execute.return_value.data = [_conversation_row(i) for i in range(500)]
        elif start == 500:
            query.execute.return_value.data = [
                _conversation_row(i) for i in range(500, 750)
            ]
        else:
            query.execute.return_value.data = []
        return query

    ordered.range.side_effect = _range_side_effect

    rows = gateway.list_conversations(user_id="user-1", limit=None)

    assert len(rows) == 750
    ordered.range.assert_any_call(0, 499)
    ordered.range.assert_any_call(500, 999)
    ordered.limit.assert_not_called()
