"""One activity claim may also fulfill one explicitly selected occurrence."""

from typing import Any


def occurrence_id(key: str, link: dict[str, Any]) -> str | None:
    return link.get("occurrence_id", key if link.get("expectation_id") else None)


def for_occurrence(state: dict[str, Any], identifier: str) -> dict[str, Any] | None:
    return next(
        (
            link
            for key, link in state["links"].items()
            if occurrence_id(key, link) == identifier
        ),
        None,
    )
