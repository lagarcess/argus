from __future__ import annotations

import json

import httpx
import pytest
from argus.domain.discovery_search import (
    SearchUnavailableError,
)
from argus.domain.discovery_search.openrouter_web_search import (
    OpenRouterWebSearchProvider,
)
from argus.domain.discovery_search.perplexity_direct import (
    DOCUMENTED_PERPLEXITY_SEARCH_COST_USD,
    PerplexityDirectProvider,
)
from argus.domain.discovery_search.selection import search_provider_for_config


def _perplexity_payload() -> dict:
    return {
        "id": "req-1",
        "results": [
            {
                "title": "Vertiv expands data center cooling",
                "url": "https://example.com/vertiv",
                "snippet": "Vertiv builds data center cooling equipment.",
                "last_updated": "2026-07-20",
            },
            {
                "title": "Bad URL result",
                "url": "http://insecure.example.com",
                "snippet": "should be dropped",
                "date": "2026-07-19",
            },
            {
                "title": "Modine partners on cooling",
                "url": "https://example.com/modine",
                "snippet": "Modine announced a cooling partnership.",
                "date": "2026-07-18",
            },
        ],
    }


def _openrouter_payload() -> dict:
    return {
        "choices": [
            {
                "message": {
                    "content": "Here are some companies.",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "url": "https://example.com/crwd",
                                "title": "CrowdStrike overview",
                                "content": "CrowdStrike is a cybersecurity vendor.",
                            },
                        },
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "url": "javascript:alert(1)",
                                "title": "Injected",
                                "content": "drop me",
                            },
                        },
                    ],
                }
            }
        ],
        "usage": {"cost": 0.0123},
    }


def _perplexity(transport: httpx.MockTransport) -> PerplexityDirectProvider:
    return PerplexityDirectProvider(api_key="test-key", transport=transport)


def _openrouter(transport: httpx.MockTransport) -> OpenRouterWebSearchProvider:
    return OpenRouterWebSearchProvider(
        api_key="test-key",
        model="test/search-model",
        transport=transport,
    )


class TestPerplexityDirect:
    def test_parses_documented_response_shape_with_source_dates(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["auth"] = request.headers.get("authorization")
            seen["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=_perplexity_payload())

        packet = _perplexity(httpx.MockTransport(handler)).search(
            "data center cooling companies", max_results=5, timeout_seconds=8.0
        )
        assert seen["url"] == "https://api.perplexity.ai/search"
        assert seen["auth"] == "Bearer test-key"
        assert seen["body"]["query"] == "data center cooling companies"
        assert seen["body"]["max_results"] == 5
        assert packet.provider_id == "perplexity_direct"
        assert [result.url for result in packet.results] == [
            "https://example.com/vertiv",
            "https://example.com/modine",
        ]
        assert packet.results[0].source_date == "2026-07-20"
        assert packet.results[1].source_date == "2026-07-18"
        assert packet.cost_usd == DOCUMENTED_PERPLEXITY_SEARCH_COST_USD
        assert packet.latency_ms >= 0

    @pytest.mark.parametrize(
        ("status_code", "expected_reason"),
        (
            (401, "authentication_failed"),
            (403, "authentication_failed"),
            (429, "http_error"),
            (503, "http_error"),
        ),
    )
    def test_http_status_raises_typed_unavailable(
        self, status_code: int, expected_reason: str
    ) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(status_code, text="boom")
        )
        with pytest.raises(SearchUnavailableError) as excinfo:
            _perplexity(transport).search("q", max_results=5, timeout_seconds=8.0)
        assert excinfo.value.reason == expected_reason

    def test_timeout_raises_typed_unavailable(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("slow", request=request)

        with pytest.raises(SearchUnavailableError) as excinfo:
            _perplexity(httpx.MockTransport(handler)).search(
                "q", max_results=5, timeout_seconds=0.01
            )
        assert excinfo.value.reason == "timeout"

    def test_malformed_json_raises_typed_unavailable(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text="not json")
        )
        with pytest.raises(SearchUnavailableError) as excinfo:
            _perplexity(transport).search("q", max_results=5, timeout_seconds=8.0)
        assert excinfo.value.reason == "malformed_response"

    def test_missing_api_key_fails_closed_without_http(self) -> None:
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, json=_perplexity_payload())

        provider = PerplexityDirectProvider(
            api_key="", transport=httpx.MockTransport(handler)
        )
        with pytest.raises(SearchUnavailableError) as excinfo:
            provider.search("q", max_results=5, timeout_seconds=8.0)
        assert excinfo.value.reason == "not_configured"
        assert calls == []

    def test_single_attempt_no_retry(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(503, text="unavailable")

        with pytest.raises(SearchUnavailableError):
            _perplexity(httpx.MockTransport(handler)).search(
                "q", max_results=5, timeout_seconds=8.0
            )
        assert len(calls) == 1


class TestOpenRouterWebSearch:
    def test_parses_annotation_citations_without_date_guarantee(self) -> None:
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["body"] = json.loads(request.content.decode("utf-8"))
            return httpx.Response(200, json=_openrouter_payload())

        packet = _openrouter(httpx.MockTransport(handler)).search(
            "cybersecurity companies", max_results=5, timeout_seconds=8.0
        )
        assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
        assert seen["body"]["model"] == "test/search-model"
        assert seen["body"]["plugins"] == [{"id": "web", "max_results": 5}]
        assert packet.provider_id == "openrouter_web_search"
        assert [result.url for result in packet.results] == ["https://example.com/crwd"]
        assert packet.results[0].source_date is None
        assert packet.cost_usd == 0.0123

    def test_uses_only_each_claim_before_a_citation_marker(self) -> None:
        example_claim = "Example Corp (EXM) is a newly listed public company."
        example_marker = "[[1]](https://example.com/exm)"
        other_claim = "Other Corp (OTH) completed a separate listing."
        other_marker = "[[2]](https://example.com/oth)"
        content = (
            f"{example_claim}{example_marker}\n{other_claim}{other_marker}"
        )
        example_start = content.index(example_marker)
        example_end = example_start + len(example_marker)
        other_start = content.index(other_marker)
        other_end = other_start + len(other_marker)
        payload = {
            "choices": [
                {
                    "message": {
                        "content": content,
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url_citation": {
                                    "url": "https://example.com/exm",
                                    "title": "Example Corp listing",
                                    "start_index": example_start,
                                    "end_index": example_end,
                                },
                            },
                            {
                                "type": "url_citation",
                                "url_citation": {
                                    "url": "https://example.com/oth",
                                    "title": "Other Corp listing",
                                    "start_index": other_start,
                                    "end_index": other_end,
                                },
                            },
                        ],
                    }
                }
            ]
        }
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )

        packet = _openrouter(transport).search(
            "recent IPOs", max_results=5, timeout_seconds=8.0
        )

        assert [result.snippet for result in packet.results] == [
            example_claim,
            other_claim,
        ]

    @pytest.mark.parametrize(
        "unsupported_claim",
        (
            "Unsupported Corp (BAD) is not documented here.",
            "Unsupported Corp.",
        ),
    )
    def test_uses_only_adjacent_same_line_claim_before_marker(
        self, unsupported_claim: str
    ) -> None:
        supported_claim = "Supported Corp (GOOD) completed an IPO."
        marker = "[[1]](https://example.com/good)"
        content = f"{unsupported_claim} {supported_claim}{marker}"
        marker_start = content.index(marker)
        payload = {
            "choices": [
                {
                    "message": {
                        "content": content,
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url_citation": {
                                    "url": "https://example.com/good",
                                    "title": "Supported Corp listing",
                                    "start_index": marker_start,
                                    "end_index": marker_start + len(marker),
                                },
                            }
                        ],
                    }
                }
            ]
        }
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )

        packet = _openrouter(transport).search(
            "recent IPOs", max_results=5, timeout_seconds=8.0
        )

        assert [result.snippet for result in packet.results] == [supported_claim]

    @pytest.mark.parametrize(
        "supported_claim",
        (
            "Example Inc. recently completed its IPO.",
            "Acme S.A. completed a public listing.",
            "U.S. Bancorp announced a public offering.",
        ),
    )
    def test_preserves_corporate_abbreviations_in_adjacent_claim(
        self, supported_claim: str
    ) -> None:
        unsupported_claim = "Unsupported Corp (BAD) is not documented here."
        marker = "[[1]](https://example.com/listing)"
        content = f"{unsupported_claim} {supported_claim}{marker}"
        marker_start = content.index(marker)
        payload = {
            "choices": [
                {
                    "message": {
                        "content": content,
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url_citation": {
                                    "url": "https://example.com/listing",
                                    "title": "Public listing",
                                    "start_index": marker_start,
                                    "end_index": marker_start + len(marker),
                                },
                            }
                        ],
                    }
                }
            ]
        }
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )

        packet = _openrouter(transport).search(
            "recent IPOs", max_results=5, timeout_seconds=8.0
        )

        assert [result.snippet for result in packet.results] == [supported_claim]

    @pytest.mark.parametrize(
        "supported_claim",
        (
            "eBay completed a public offering.",
            "iRobot completed a public offering.",
            "monday.com completed a public offering.",
        ),
    )
    def test_separates_claim_before_lowercase_styled_company_name(
        self, supported_claim: str
    ) -> None:
        unsupported_claim = "Unsupported Inc."
        marker = "[[1]](https://example.com/listing)"
        content = f"{unsupported_claim} {supported_claim}{marker}"
        marker_start = content.index(marker)
        payload = {
            "choices": [
                {
                    "message": {
                        "content": content,
                        "annotations": [
                            {
                                "type": "url_citation",
                                "url_citation": {
                                    "url": "https://example.com/listing",
                                    "title": "Public listing",
                                    "start_index": marker_start,
                                    "end_index": marker_start + len(marker),
                                },
                            }
                        ],
                    }
                }
            ]
        }
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        )

        packet = _openrouter(transport).search(
            "recent IPOs", max_results=5, timeout_seconds=8.0
        )

        assert [result.snippet for result in packet.results] == [supported_claim]

    def test_missing_model_fails_closed_without_http(self) -> None:
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(200, json=_openrouter_payload())

        provider = OpenRouterWebSearchProvider(
            api_key="test-key", model="", transport=httpx.MockTransport(handler)
        )
        with pytest.raises(SearchUnavailableError) as excinfo:
            provider.search("q", max_results=5, timeout_seconds=8.0)
        assert excinfo.value.reason == "not_configured"
        assert calls == []

    def test_http_error_and_malformed_shape_raise_typed_unavailable(self) -> None:
        with pytest.raises(SearchUnavailableError) as excinfo:
            _openrouter(
                httpx.MockTransport(lambda request: httpx.Response(429, text="rate"))
            ).search("q", max_results=5, timeout_seconds=8.0)
        assert excinfo.value.reason == "http_error"

        with pytest.raises(SearchUnavailableError) as excinfo:
            _openrouter(
                httpx.MockTransport(
                    lambda request: httpx.Response(200, json={"choices": []})
                )
            ).search("q", max_results=5, timeout_seconds=8.0)
        assert excinfo.value.reason == "malformed_response"


class TestProviderSelection:
    def test_known_provider_ids_resolve(self, monkeypatch) -> None:
        monkeypatch.setenv("PERPLEXITY_API_KEY", "k")
        monkeypatch.setenv("OPENROUTER_API_KEY", "k")
        monkeypatch.setenv("ARGUS_DISCOVERY_OPENROUTER_SEARCH_MODEL", "m/x")
        assert (
            search_provider_for_config(provider_id="perplexity_direct").__class__.__name__
            == "PerplexityDirectProvider"
        )
        assert (
            search_provider_for_config(
                provider_id="openrouter_web_search"
            ).__class__.__name__
            == "OpenRouterWebSearchProvider"
        )

    def test_unknown_provider_id_fails_closed(self) -> None:
        with pytest.raises(SearchUnavailableError) as excinfo:
            search_provider_for_config(provider_id="mystery_engine")
        assert excinfo.value.reason == "not_configured"

    def test_hosted_openrouter_search_uses_scoped_traffic_key(
        self,
        monkeypatch,
    ) -> None:
        from argus.domain.discovery_search import openrouter_web_search
        from argus.llm.openrouter_key_policy import openrouter_traffic_class

        seen: dict[str, object] = {}

        def fake_post_json(**kwargs):
            seen.update(kwargs)
            return {"choices": [{"message": {"annotations": []}}]}

        monkeypatch.setattr(openrouter_web_search, "post_json", fake_post_json)
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        monkeypatch.setenv("ARGUS_PROD_OPENROUTER_API_KEY", "registered-key")
        monkeypatch.setenv("ARGUS_GUEST_ACCESS_OPENROUTER_API_KEY", "guest-key")
        monkeypatch.setenv("ARGUS_DISCOVERY_OPENROUTER_SEARCH_MODEL", "m/x")

        with openrouter_traffic_class("guest"):
            provider = search_provider_for_config(
                provider_id="openrouter_web_search"
            )
            provider.search("q", max_results=1, timeout_seconds=1.0)

        assert seen["headers"] == {"Authorization": "Bearer guest-key"}
