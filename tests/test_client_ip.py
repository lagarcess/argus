"""Trusted client-IP helper: Cloudflare/Render header, never X-Forwarded-For."""

from __future__ import annotations

from unittest.mock import patch

from argus.api.client_ip import (
    DEFAULT_TRUSTED_CLIENT_IP_HEADER,
    reset_trusted_header_fallback_warning_for_tests,
    resolve_client_ip,
    trusted_client_ip_header_name,
)
from argus.api.guest_access import client_identity
from argus.domain.visitor_usage import guest_session_compute_key
from starlette.requests import Request


def _request(
    *,
    headers: dict[str, str] | None = None,
    peer: str | None = "192.0.2.10",
) -> Request:
    scope_headers = [
        (key.lower().encode(), value.encode())
        for key, value in (headers or {}).items()
    ]
    scope: dict[str, object] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": scope_headers,
        "server": ("testserver", 80),
    }
    if peer is not None:
        scope["client"] = (peer, 12345)
    return Request(scope)


def test_trusted_header_name_defaults_to_cf_connecting_ip(
    monkeypatch,
) -> None:
    monkeypatch.delenv("ARGUS_TRUSTED_CLIENT_IP_HEADER", raising=False)
    assert trusted_client_ip_header_name() == DEFAULT_TRUSTED_CLIENT_IP_HEADER
    monkeypatch.setenv("ARGUS_TRUSTED_CLIENT_IP_HEADER", "True-Client-IP")
    assert trusted_client_ip_header_name() == "True-Client-IP"


def test_helper_uses_trusted_header_and_ignores_xff() -> None:
    request = _request(
        headers={
            "X-Forwarded-For": "198.51.100.1, 203.0.113.10",
            "CF-Connecting-IP": "203.0.113.50",
        },
        peer="192.0.2.10",
    )
    assert resolve_client_ip(request) == "203.0.113.50"
    assert client_identity(request) == "203.0.113.50"


def test_helper_ignores_xff_when_trusted_header_is_absent() -> None:
    request = _request(
        headers={"X-Forwarded-For": "198.51.100.1, 203.0.113.10"},
        peer="192.0.2.10",
    )
    assert resolve_client_ip(request) == "192.0.2.10"


def test_helper_falls_back_to_unknown_without_peer_or_trusted_header() -> None:
    request = _request(headers={"X-Forwarded-For": "198.51.100.1"}, peer=None)
    assert resolve_client_ip(request) == "unknown"


def test_session_compute_key_is_the_authenticated_guest_id() -> None:
    assert (
        guest_session_compute_key("00000000-0000-4000-8000-000000000051")
        == "session:00000000-0000-4000-8000-000000000051"
    )
    assert guest_session_compute_key("  ") == "session:unknown"


def test_configured_header_is_the_only_trusted_read(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_TRUSTED_CLIENT_IP_HEADER", "True-Client-IP")
    request = _request(
        headers={
            "CF-Connecting-IP": "203.0.113.50",
            "True-Client-IP": "203.0.113.77",
            "X-Forwarded-For": "198.51.100.1",
        }
    )
    assert resolve_client_ip(request) == "203.0.113.77"


def _hosted_env(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_PERSISTENCE_MODE", "supabase")
    monkeypatch.setenv("ARGUS_DEV_MEMORY_FALLBACK", "false")
    reset_trusted_header_fallback_warning_for_tests()


def test_hosted_fallback_warns_once_per_minute(monkeypatch) -> None:
    _hosted_env(monkeypatch)
    request = _request(
        headers={"X-Forwarded-For": "198.51.100.1"},
        peer="10.0.0.8",
    )
    with patch("argus.api.client_ip.logger.warning") as warning:
        assert resolve_client_ip(request) == "10.0.0.8"
        assert resolve_client_ip(request) == "10.0.0.8"
        warning.assert_called_once()
        assert (
            warning.call_args.args[0]
            == "Trusted client-IP header missing; using socket peer"
        )
        assert warning.call_args.kwargs["header"] == "CF-Connecting-IP"
        assert warning.call_args.kwargs["peer"] == "10.0.0.8"


def test_local_dev_fallback_does_not_warn(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_PERSISTENCE_MODE", "memory")
    monkeypatch.setenv("ARGUS_DEV_MEMORY_FALLBACK", "true")
    reset_trusted_header_fallback_warning_for_tests()
    request = _request(headers={"X-Forwarded-For": "198.51.100.1"})
    with patch("argus.api.client_ip.logger.warning") as warning:
        assert resolve_client_ip(request) == "192.0.2.10"
        warning.assert_not_called()


def test_hosted_trusted_header_does_not_warn(monkeypatch) -> None:
    _hosted_env(monkeypatch)
    request = _request(headers={"CF-Connecting-IP": "203.0.113.50"})
    with patch("argus.api.client_ip.logger.warning") as warning:
        assert resolve_client_ip(request) == "203.0.113.50"
        warning.assert_not_called()
