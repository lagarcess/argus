from __future__ import annotations

from datetime import datetime, timezone

import pytest
from argus.domain.discovery_search import (
    MAX_RESULTS,
    DiscoverySearchConfig,
    SearchProvider,
    SearchResult,
    SearchResultPacket,
    SearchUnavailableError,
    discovery_search_config,
    sanitize_search_result,
)
from pydantic import ValidationError


def _packet(results: list[SearchResult]) -> SearchResultPacket:
    return SearchResultPacket(
        results=results,
        retrieved_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
        latency_ms=120,
        provider_id="test_provider",
        cost_usd=0.005,
    )


class TestSanitizeSearchResult:
    def test_valid_https_result_is_kept_and_trimmed(self) -> None:
        result = sanitize_search_result(
            title="  CrowdStrike expands platform  ",
            url="https://example.com/article",
            snippet="  CrowdStrike is a cybersecurity vendor.  ",
            source_date="2026-07-20",
        )
        assert result is not None
        assert result.title == "CrowdStrike expands platform"
        assert result.snippet == "CrowdStrike is a cybersecurity vendor."
        assert result.url == "https://example.com/article"
        assert result.source_date == "2026-07-20"

    def test_non_https_url_is_rejected(self) -> None:
        for url in (
            "http://example.com/a",
            "javascript:alert(1)",
            "ftp://example.com",
            "",
            "example.com/no-scheme",
        ):
            assert sanitize_search_result(title="t", url=url, snippet="s") is None

    def test_over_long_url_is_rejected(self) -> None:
        url = "https://example.com/" + "a" * 600
        assert sanitize_search_result(title="t", url=url, snippet="s") is None

    def test_title_and_snippet_are_truncated_to_bounds(self) -> None:
        result = sanitize_search_result(
            title="t" * 500,
            url="https://example.com",
            snippet="s" * 5000,
        )
        assert result is not None
        assert len(result.title) == 200
        assert len(result.snippet) == 1000

    def test_control_characters_are_stripped(self) -> None:
        result = sanitize_search_result(
            title="Good\x00Title\x1b[31m",
            url="https://example.com",
            snippet="line one\x0bline two\x7f",
        )
        assert result is not None
        assert "\x00" not in result.title
        assert "\x1b" not in result.title
        assert "\x0b" not in result.snippet
        assert "\x7f" not in result.snippet

    def test_invalid_source_date_is_dropped_not_fatal(self) -> None:
        result = sanitize_search_result(
            title="t",
            url="https://example.com",
            snippet="s",
            source_date="not-a-date",
        )
        assert result is not None
        assert result.source_date is None

    def test_iso_datetime_source_date_is_normalized_to_date(self) -> None:
        result = sanitize_search_result(
            title="t",
            url="https://example.com",
            snippet="s",
            source_date="2026-07-20T14:00:00Z",
        )
        assert result is not None
        assert result.source_date == "2026-07-20"


class TestSearchResultPacket:
    def test_packet_caps_results_at_five(self) -> None:
        results = [
            sanitize_search_result(
                title=f"t{i}", url=f"https://example.com/{i}", snippet="s"
            )
            for i in range(9)
        ]
        packet = _packet([r for r in results if r is not None])
        assert MAX_RESULTS == 5
        assert len(packet.results) == 5

    def test_packet_rejects_negative_latency(self) -> None:
        with pytest.raises(ValidationError):
            SearchResultPacket(
                results=[],
                retrieved_at=datetime(2026, 7, 26, tzinfo=timezone.utc),
                latency_ms=-1,
                provider_id="p",
                cost_usd=None,
            )


class TestSearchUnavailableError:
    def test_carries_typed_reason(self) -> None:
        error = SearchUnavailableError(reason="timeout")
        assert error.reason == "timeout"
        assert isinstance(error, Exception)

    def test_unknown_reason_fails_closed(self) -> None:
        with pytest.raises(ValueError):
            SearchUnavailableError(reason="weird_new_reason")


class TestDiscoverySearchConfig:
    def test_flag_defaults_off_and_bounds_default(self, monkeypatch) -> None:
        for name in (
            "ARGUS_GROUNDED_DISCOVERY_ENABLED",
            "ARGUS_DISCOVERY_SEARCH_PROVIDER",
            "ARGUS_DISCOVERY_SEARCH_TIMEOUT_SECONDS",
            "ARGUS_DISCOVERY_MAX_CANDIDATES",
            "ARGUS_DISCOVERY_HOURLY_LIMIT",
            "ARGUS_DISCOVERY_DAILY_LIMIT",
        ):
            monkeypatch.delenv(name, raising=False)
        config = discovery_search_config()
        assert config.enabled is False
        assert config.timeout_seconds == 8.0
        assert config.max_candidates == 5
        assert config.hourly_limit == 10
        assert config.daily_limit == 25

    def test_flag_parses_truthy_values(self, monkeypatch) -> None:
        for raw in ("true", "1", "yes", "on", " TRUE "):
            monkeypatch.setenv("ARGUS_GROUNDED_DISCOVERY_ENABLED", raw)
            assert discovery_search_config().enabled is True
        for raw in ("false", "0", "off", "no", "", "banana"):
            monkeypatch.setenv("ARGUS_GROUNDED_DISCOVERY_ENABLED", raw)
            assert discovery_search_config().enabled is False

    def test_bounds_are_clamped_and_bad_values_fall_back(self, monkeypatch) -> None:
        monkeypatch.setenv("ARGUS_DISCOVERY_SEARCH_TIMEOUT_SECONDS", "-3")
        monkeypatch.setenv("ARGUS_DISCOVERY_MAX_CANDIDATES", "50")
        monkeypatch.setenv("ARGUS_DISCOVERY_HOURLY_LIMIT", "not-a-number")
        config = discovery_search_config()
        assert config.timeout_seconds == 8.0
        assert config.max_candidates == 5
        assert config.hourly_limit == 10
        monkeypatch.setenv("ARGUS_DISCOVERY_MAX_CANDIDATES", "0")
        assert discovery_search_config().max_candidates == 1

    def test_provider_id_is_normalized(self, monkeypatch) -> None:
        monkeypatch.setenv("ARGUS_DISCOVERY_SEARCH_PROVIDER", "  Perplexity_Direct ")
        assert discovery_search_config().provider_id == "perplexity_direct"

    def test_config_is_a_frozen_snapshot(self, monkeypatch) -> None:
        monkeypatch.setenv("ARGUS_GROUNDED_DISCOVERY_ENABLED", "true")
        config = discovery_search_config()
        with pytest.raises(ValidationError):
            config.enabled = False  # type: ignore[misc]


class TestSearchProviderProtocol:
    def test_protocol_accepts_conforming_fake(self) -> None:
        class FakeProvider:
            def search(
                self, query: str, *, max_results: int, timeout_seconds: float
            ) -> SearchResultPacket:
                del query, max_results, timeout_seconds
                return _packet([])

        provider: SearchProvider = FakeProvider()
        packet = provider.search("q", max_results=5, timeout_seconds=8.0)
        assert packet.results == ()

    def test_config_shape_is_stable(self) -> None:
        config = DiscoverySearchConfig(
            enabled=True,
            provider_id="perplexity_direct",
            timeout_seconds=8.0,
            max_candidates=5,
            hourly_limit=10,
            daily_limit=25,
        )
        assert config.enabled is True
