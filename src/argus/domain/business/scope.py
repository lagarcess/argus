"""Whose Business records a request reads and writes.

Every Business route and the WhatsApp intake destination get their scope from
``resolve_business_scope`` and nowhere else. No route accepts a scope, a space
or an owner from the client.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BusinessScope:
    person_id: str
    space_id: str | None


def resolve_business_scope(person_id: str) -> BusinessScope:
    """The signed-in person's Business scope.

    Isolation is pending the founder-approved ownership boundary
    (docs/specs/lanes/cuadrao-business-boundary-proposal.md, #819). Until it
    is approved ``space_id`` is None and Business reads and writes the
    person's own records, the same rows Personal sees. When a boundary is
    approved this is the one place that starts returning a space.
    """

    return BusinessScope(person_id=person_id, space_id=None)
