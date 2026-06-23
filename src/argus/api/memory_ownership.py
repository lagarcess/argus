from __future__ import annotations

from collections.abc import Mapping


def memory_object_visible(
    *,
    owner_map: Mapping[str, str],
    object_id: str,
    user_id: str,
) -> bool:
    owner_id = owner_map.get(object_id)
    return owner_id is None or owner_id == user_id
