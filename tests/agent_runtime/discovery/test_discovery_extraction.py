from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest
from argus.agent_runtime.discovery import extraction as extraction_module
from argus.agent_runtime.discovery.extraction import extract_candidates
from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest
from argus.domain.research.search import SearchResultPacket, sanitize_search_result


def _packet() -> SearchResultPacket:
    result = sanitize_search_result(
        title="Cybersecurity leaders",
        url="https://example.com/a",
        snippet="CrowdStrike leads.",
        source_date="2026-07-20",
    )
    return SearchResultPacket(
        results=[result] if result else [],
        retrieved_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
        latency_ms=100,
        provider_id="fake",
        cost_usd=0.005,
    )


class TestExtractionFailureContainment:
    @pytest.mark.asyncio()
    async def test_provider_call_raising_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _raise(**kwargs: Any):
            raise RuntimeError("terminal structured-call failure")

        monkeypatch.setattr(extraction_module, "invoke_openrouter_json_schema", _raise)
        result = await extract_candidates(
            request=AssetDiscoveryRequest(
                relationship="category",
                category_description="cybersecurity stocks",
            ),
            packet=_packet(),
            language="en",
        )
        assert result is None
