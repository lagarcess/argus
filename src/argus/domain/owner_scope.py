"""Whose records a read or write sees: the person's Personal records or one Business space.

A root row (account, source connection, import event, conversation) stores
``owner_space_id``. Null is Personal; a Business row stores its space id. The
predicate text lives only in ``sql_predicate`` and the in-memory twins use
``holds``, so the null rule has one owner. Every scoped reader and writer takes
``scope`` as a required keyword: a caller states which side it means.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Personal:
    pass


@dataclass(frozen=True)
class BusinessSpace:
    space_id: str


OwnerScope = Personal | BusinessSpace
PERSONAL = Personal()


def space_id(scope: OwnerScope) -> str | None:
    """The value a row in this scope stores in ``owner_space_id``."""

    return scope.space_id if isinstance(scope, BusinessSpace) else None


def scope_of(stored_space_id: object) -> OwnerScope:
    """The scope a stored ``owner_space_id`` names."""

    return PERSONAL if stored_space_id is None else BusinessSpace(str(stored_space_id))


def holds(scope: OwnerScope, stored_space_id: object) -> bool:
    """Whether a row storing ``stored_space_id`` belongs to ``scope``."""

    return scope_of(stored_space_id) == scope


def sql_predicate(scope: OwnerScope, column: str) -> tuple[str, tuple[str, ...]]:
    """``(condition, params)`` keeping rows of ``scope``; ``column`` is a code constant."""

    if isinstance(scope, BusinessSpace):
        return f"{column} = %s", (scope.space_id,)
    return f"{column} is null", ()
