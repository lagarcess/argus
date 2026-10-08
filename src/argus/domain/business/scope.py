"""Whose Business records a request reads and writes.

Every Business route and the WhatsApp intake destination get their scope from
``resolve_business_scope`` and nowhere else. No route accepts a scope, a space
or an owner from the client.
"""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.business.spaces import SpaceStore
from argus.domain.owner_scope import BusinessSpace


@dataclass(frozen=True)
class BusinessScope:
    person_id: str
    owner: BusinessSpace


def resolve_business_scope(spaces: SpaceStore, person_id: str) -> BusinessScope | None:
    """The signed-in person's open Business space, or None before they start one.

    A space belongs only to the person who created it; nothing here reads a
    membership or a client-supplied id.
    """

    space = spaces.open_space(person_id)
    if space is None:
        return None
    return BusinessScope(person_id=person_id, owner=BusinessSpace(space.id))
