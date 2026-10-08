"""Whose Business records a request reads and writes.

Every Business route and the WhatsApp intake destination get their scope from
``resolve_business_scope`` and nowhere else. No route accepts a scope, a space
or an owner from the client.
"""

from __future__ import annotations

from dataclasses import dataclass

from argus.domain.owner_scope import PERSONAL, OwnerScope


@dataclass(frozen=True)
class BusinessScope:
    person_id: str
    owner: OwnerScope


def resolve_business_scope(person_id: str) -> BusinessScope:
    """The signed-in person's Business scope.

    Until the Business space resolver lands, Business reads and writes the
    person's Personal records, the same rows Personal sees.
    """

    return BusinessScope(person_id=person_id, owner=PERSONAL)
