"""Tool declarations and their lifecycle stay usable without backtest bodies."""

from __future__ import annotations

import pytest

from tests.agent_runtime.test_shared_loop_import_boundary import _run_probe


@pytest.mark.parametrize(
    "module",
    (
        "argus.domain.tool_contracts",
        "argus.domain.tool_declaration",
        "argus.domain.tool_job_binding",
        "argus.domain.pending_artifacts",
    ),
)
def test_tool_contract_import_refuses_backtest_and_catalog_dependencies(module: str) -> None:
    # Reuse the existing fresh-process guard, including its network prohibition.
    _run_probe(module)


def test_effective_catalog_derives_research_availability_from_shared_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.agent_runtime.research_tools import get_research_declarations
    from argus.domain.capability_registry import get_tool_catalog

    research_handlers = {item.handler for item in get_research_declarations()}
    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    disabled = get_tool_catalog()
    assert not research_handlers.intersection(item.handler for item in disabled.declarations)
    assert research_handlers.issubset(
        item.handler for item in get_tool_catalog(include_unavailable=True).declarations
    )

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "true")
    enabled = get_tool_catalog()
    assert research_handlers.issubset(item.handler for item in enabled.declarations)

    monkeypatch.setenv("ARGUS_RESEARCH_RAIL_ENABLED", "false")
    assert get_tool_catalog().capability_text() == disabled.capability_text()
