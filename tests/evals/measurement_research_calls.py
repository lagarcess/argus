"""Observe interpreter research need and provider attempts without changing either."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator
from unittest.mock import patch

from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.evals.measurement_assertions import _compare


class ObservedInterpreter:
    def __init__(self, delegate: Any) -> None:
        self.delegate = delegate
        self.interpretation: Any = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    async def ainvoke(self, request: Any) -> Any:
        self.interpretation = await self.delegate.ainvoke(request)
        return self.interpretation

    def research_need(self) -> bool | None:
        query = getattr(self.interpretation, "research_query", None)
        return getattr(query, "requires_new_facts", None)


@contextmanager
def capture_research_attempts() -> Iterator[list[str]]:
    # At the actual provider HTTP owner: cache reads, typed cards and citation
    # absence cannot prove that a network request did not happen. Retain no URL,
    # headers, prompt, body or provider text. Retried sends count separately.
    attempts: list[str] = []
    original = PerplexityAgentClient._send

    def send(client: Any, *args: Any, **kwargs: Any) -> Any:
        attempts.append("perplexity_agent_send")
        return original(client, *args, **kwargs)

    with patch.object(PerplexityAgentClient, "_send", send):
        yield attempts


def _research_outcome(patch: dict[str, Any]) -> dict[str, Any] | None:
    """The typed research sidecar as the eval reads it, or None when the turn
    took no rail: published is the absence of a degraded code, rows and
    sources are counts of what the sidecar carries."""
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


def _compare_research(expected: dict[str, Any], actual: Any, failures: list[str]) -> None:
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
