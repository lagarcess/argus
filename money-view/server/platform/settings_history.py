"""Settings history composes current and older canonical conversation owners."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from ..store import Store
from .assistant_contracts import State, TrashAll
from .common import Context, get_context, get_store, require_owner

router = APIRouter(prefix="/settings/history")
Source = Literal["chat", "assistant"]
DB = Annotated[Store, Depends(get_store)]
CTX = Annotated[Context, Depends(get_context)]
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]


@router.get("")
def history(
    source: Source,
    store: DB,
    context: CTX,
    state: State = "archived",
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    from . import assistant, chat

    owner = chat if source == "chat" else assistant
    page = owner.list_conversations(store, context, state, limit=limit, offset=offset)
    return {"source": source, **page}


@router.post("/trash-all")
def trash_all(payload: TrashAll, store: DB, context: CTX):
    from . import assistant, chat

    require_owner(context)
    with store.transaction() as bound:
        older = assistant.trash_all(payload, bound, context)["trashed"]
        with bound.connection(write=True) as connection:
            current = chat.trash_all_conversations(connection, context)
    return {
        "trashed": older + current,
        "counts": {"chat": current, "assistant": older},
        "scope": "household",
        "restorable": True,
    }
