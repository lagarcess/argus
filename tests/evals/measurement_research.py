"""Observe published research through the same bound delivery owners."""

from __future__ import annotations

from typing import Any

from tests.evals.measurement_assertions import _compare
from tests.evals.measurement_selection import completed_research_deliveries


def research_outcome(
    patch: dict[str, Any],
    *,
    calls: list[dict] | None = None,
    dispatch_patch: dict | None = None,
) -> dict[str, Any] | None:
    """Read completed calls, or the legacy sidecar when no call inventory is given."""
    if calls is not None:
        observations = []
        for card, result, effect in completed_research_deliveries(
            calls, dispatch_patch or {}
        ):
            observed = research_outcome(effect)
            if observed is not None:
                observations.append(
                    {
                        **observed,
                        "call_id": card.call_id,
                        "rows": len(result.rows),
                        "sources": len(result.sources),
                    }
                )
        if not observations:
            return None
        published = any(item["published"] for item in observations)
        shapes = {item["shape"] for item in observations}
        return {
            "published": published,
            "degraded_code": None if published else observations[0]["degraded_code"],
            "shape": shapes.pop() if len(shapes) == 1 else None,
            "rows": sum(item["rows"] for item in observations),
            "sources": sum(item["sources"] for item in observations),
            "calls": observations,
        }
    sidecar = patch.get("research")
    if not isinstance(sidecar, dict):
        return None
    degraded = sidecar.get("degraded")
    return {
        "published": not degraded,
        "degraded_code": degraded.get("code") if isinstance(degraded, dict) else None,
        "shape": sidecar.get("shape"),
        "rows": len(sidecar.get("rows") or []),
        "sources": len(sidecar.get("sources") or []),
    }


def compare_research(expected: dict[str, Any], actual: Any, failures: list[str]) -> None:
    if not isinstance(actual, dict):
        failures.append(f"research: expected a research sidecar, got {actual!r}")
        return
    _compare(
        "research.published", expected.get("published"), actual.get("published"), failures
    )
    _compare("research.shape", expected.get("shape"), actual.get("shape"), failures)
    # An expected row count is a floor: a green case promises at least that
    # many typed figures, and the provider is free to state more.
    rows = expected.get("rows")
    if rows is not None and (actual.get("rows") or 0) < rows:
        failures.append(
            f"research.rows: expected at least {rows}, got {actual.get('rows')!r}"
        )
