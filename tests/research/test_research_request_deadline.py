"""Every research request ends by its deadline at the socket layer (#609).

The provider is a real server on 127.0.0.1 that answers, refuses, trickles one
byte at a time, or speaks TLS, and the resolver is stubbed: no test here reaches
real DNS.
"""

from __future__ import annotations

import errno
import json
import select
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
from argus.domain.research import perplexity_agent
from argus.domain.research.config import RESEARCH_CONFIG_SPECS
from argus.domain.research.contracts import ResearchUnavailableError
from argus.domain.research.perplexity_agent import PerplexityAgentClient

from tests.research.conftest import agent_response

FAST = RESEARCH_CONFIG_SPECS["fast"]
QUESTION = "What is Apple trading at right now?"


class TricklingProvider:
    """A real socket server. Each connection plays the next step; a trickle
    sends one byte at a time, so no single connect, write or read timeout fires."""

    def __init__(self, steps: list[str], *, tls: ssl.SSLContext | None = None) -> None:
        self.steps = list(steps)
        self.connections = 0
        self.closed_by_client_at: float | None = None
        self._tls = tls
        self._stop = threading.Event()
        self._listener = socket.create_server(("127.0.0.1", 0))
        threading.Thread(target=self._serve, daemon=True).start()

    @property
    def port(self) -> int:
        return self._listener.getsockname()[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1/agent"

    def _serve(self) -> None:
        try:
            while self.steps and not self._stop.is_set():
                conn, _ = self._listener.accept()
                if self._tls is not None:
                    try:
                        conn = self._tls.wrap_socket(conn, server_side=True)
                    except OSError:
                        # A client that refused the certificate plays no step.
                        conn.close()
                        continue
                self.connections += 1
                with conn:
                    self._read_request(conn)
                    self._play(conn, self.steps.pop(0))
        except OSError:
            return

    @staticmethod
    def _read_request(conn: socket.socket) -> None:
        data = b""
        while b"\r\n\r\n" not in data:
            data += conn.recv(65536)
        head, _, body = data.partition(b"\r\n\r\n")
        length = next(
            (
                int(line.split(b":", 1)[1])
                for line in head.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            ),
            0,
        )
        while len(body) < length:
            body += conn.recv(65536)

    def _play(self, conn: socket.socket, step: str) -> None:
        if step == "answer":
            body = json.dumps(agent_response()).encode()
            conn.sendall(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                + f"Content-Length: {len(body)}\r\n\r\n".encode()
                + body
            )
            return
        if step == "503":
            conn.sendall(
                b"HTTP/1.1 503 Service Unavailable\r\n"
                b"Retry-After: 0\r\nContent-Length: 0\r\n\r\n"
            )
            return
        conn.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Content-Length: 100000\r\n\r\n"
        )
        started = time.monotonic()
        try:
            while time.monotonic() - started < 10 and not self._stop.is_set():
                conn.sendall(b" ")
                time.sleep(0.05)
        except OSError:
            self.closed_by_client_at = time.monotonic()

    def close(self) -> None:
        self._stop.set()
        self._listener.close()


@pytest.mark.parametrize(
    "steps", [["trickle"], ["503", "trickle"]], ids=["first_attempt", "retried_attempt"]
)
def test_a_trickled_answer_ends_the_request_itself_at_the_deadline(
    monkeypatch: pytest.MonkeyPatch, steps: list[str]
) -> None:
    ceiling = 0.5
    server = TricklingProvider(steps)
    monkeypatch.setattr(perplexity_agent, "PERPLEXITY_AGENT_URL", server.url)
    unpriced: list[Any] = []
    monkeypatch.setattr(perplexity_agent, "record_unpriced_spend", unpriced.append)
    client = PerplexityAgentClient("k")
    try:
        started = time.monotonic()
        with pytest.raises(ResearchUnavailableError) as raised:
            client.run_research(
                QUESTION, FAST.model_copy(update={"timeout_seconds": ceiling})
            )
        elapsed = time.monotonic() - started
        for _ in range(100):
            if server.closed_by_client_at is not None:
                break
            time.sleep(0.02)
    finally:
        server.close()

    assert raised.value.reason == "timeout" and raised.value.sent
    assert elapsed < ceiling + 2.0, "a trickle holds the request for ten seconds"
    # The request ended itself: no socket or worker is left open behind the call.
    assert server.closed_by_client_at is not None
    assert server.closed_by_client_at - started < ceiling + 2.0
    assert server.connections == len(steps)
    assert [spend.reason for spend in unpriced] == ["unanswered_attempt"]


def test_a_stalled_host_lookup_cannot_hold_a_request_past_its_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ceiling = 0.5
    release = threading.Event()
    real_lookup = socket.getaddrinfo

    def lookup(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host != "provider.test":
            return real_lookup(host, *args, **kwargs)
        # Never a real lookup: on macOS one leaves Network.framework state that
        # crashes every later forked child in its atfork handler.
        release.wait(10)
        raise socket.gaierror(socket.EAI_NONAME, "stalled lookup released")

    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    monkeypatch.setattr(
        perplexity_agent, "PERPLEXITY_AGENT_URL", "http://provider.test/v1/agent"
    )
    unpriced: list[Any] = []
    monkeypatch.setattr(perplexity_agent, "record_unpriced_spend", unpriced.append)
    client = PerplexityAgentClient("k")
    try:
        started = time.monotonic()
        with pytest.raises(ResearchUnavailableError) as raised:
            client.run_research(
                QUESTION, FAST.model_copy(update={"timeout_seconds": ceiling})
            )
        elapsed = time.monotonic() - started
    finally:
        release.set()

    assert raised.value.reason == "timeout" and not raised.value.sent
    assert elapsed < ceiling + 2.0, "a stalled lookup holds the request for ten seconds"
    assert unpriced == []


def test_a_refused_address_hands_the_time_left_to_the_next_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = TricklingProvider(["answer"])
    closed = socket.create_server(("127.0.0.1", 0))
    refused_port = closed.getsockname()[1]
    closed.close()
    real_lookup = socket.getaddrinfo

    def lookup(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if host != "provider.test":
            return real_lookup(host, port, *args, **kwargs)
        # The first address refuses the connection; the second is the provider.
        return real_lookup("127.0.0.1", refused_port, *args, **kwargs) + real_lookup(
            "127.0.0.1", server.port, *args, **kwargs
        )

    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    monkeypatch.setattr(
        perplexity_agent, "PERPLEXITY_AGENT_URL", "http://provider.test/v1/agent"
    )
    try:
        packet = PerplexityAgentClient("k").run_research(
            QUESTION, FAST.model_copy(update={"timeout_seconds": 5.0})
        )
    finally:
        server.close()

    assert packet.answer_markdown.startswith("Apple")
    assert server.connections == 1


def test_a_resolved_address_is_connected_without_a_second_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = TricklingProvider(["answer"])
    real_lookup = socket.getaddrinfo
    numeric_lookups: list[Any] = []

    def lookup(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if host == "provider.test":
            return real_lookup("127.0.0.1", server.port, *args, **kwargs)
        if host == "127.0.0.1":
            # Looking up the address already resolved would stall here.
            numeric_lookups.append(port)
            time.sleep(10)
        return real_lookup(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    monkeypatch.setattr(
        perplexity_agent, "PERPLEXITY_AGENT_URL", "http://provider.test/v1/agent"
    )
    ceiling = 2.0
    try:
        started = time.monotonic()
        packet = PerplexityAgentClient("k").run_research(
            QUESTION, FAST.model_copy(update={"timeout_seconds": ceiling})
        )
        elapsed = time.monotonic() - started
    finally:
        server.close()

    assert packet.answer_markdown.startswith("Apple")
    assert numeric_lookups == []
    assert elapsed < ceiling


def self_signed_certificate(directory: Path, host: str) -> tuple[str, str]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)])
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = directory / "cert.pem", directory / "key.pem"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return str(cert_path), str(key_path)


def test_a_tls_answer_travels_the_owned_socket_and_checks_the_host_name(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cert, key = self_signed_certificate(tmp_path, "provider.test")
    server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_tls.load_cert_chain(cert, key)
    server = TricklingProvider(["answer"], tls=server_tls)
    real_lookup = socket.getaddrinfo

    def lookup(host: Any, port: Any, *args: Any, **kwargs: Any) -> Any:
        if host in ("provider.test", "impostor.test"):
            return real_lookup("127.0.0.1", server.port, *args, **kwargs)
        return real_lookup(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", lookup)
    # The production transport trusts this certificate, and nothing else changes.
    monkeypatch.setenv("SSL_CERT_FILE", cert)
    try:
        monkeypatch.setattr(
            perplexity_agent, "PERPLEXITY_AGENT_URL", "https://impostor.test/v1/agent"
        )
        with pytest.raises(ResearchUnavailableError) as refused:
            PerplexityAgentClient("k").run_research(
                QUESTION, FAST.model_copy(update={"timeout_seconds": 1.5})
            )
        monkeypatch.setattr(
            perplexity_agent, "PERPLEXITY_AGENT_URL", "https://provider.test/v1/agent"
        )
        packet = PerplexityAgentClient("k").run_research(
            QUESTION, FAST.model_copy(update={"timeout_seconds": 5.0})
        )
    finally:
        server.close()

    # Same address, wrong name: the certificate check still refuses it.
    assert refused.value.reason == "transport" and not refused.value.sent
    assert "certificate verify failed" in (refused.value.detail or "").lower()
    assert packet.answer_markdown.startswith("Apple")
    assert server.connections == 1


class _NoSockets:
    """The socket module, except that no new socket can be created."""

    def __getattr__(self, name: str) -> Any:
        return getattr(socket, name)

    @staticmethod
    def socket(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError(errno.EMFILE, "Too many open files")


def test_a_socket_that_cannot_be_created_ends_on_a_typed_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(perplexity_agent, "socket", _NoSockets())
    monkeypatch.setattr(
        perplexity_agent, "PERPLEXITY_AGENT_URL", "http://127.0.0.1:9/v1/agent"
    )
    unpriced: list[Any] = []
    monkeypatch.setattr(perplexity_agent, "record_unpriced_spend", unpriced.append)

    with pytest.raises(ResearchUnavailableError) as raised:
        PerplexityAgentClient("k").run_research(
            QUESTION, FAST.model_copy(update={"timeout_seconds": 1.0})
        )

    assert raised.value.reason == "transport" and not raised.value.sent
    assert "Too many open files" in (raised.value.detail or "")
    assert unpriced == []


def test_a_closed_socket_fails_as_a_typed_read_and_write_error() -> None:
    backend = perplexity_agent._DeadlineBackend(time.monotonic() + 5.0, time.monotonic)
    left, right = socket.socketpair()
    right.close()
    left.close()
    stream = perplexity_agent._DeadlineStream(left, backend)

    with pytest.raises(httpx.ReadError):
        stream.read(1024)
    with pytest.raises(httpx.WriteError):
        stream.write(b"request")


def test_readability_is_checked_without_select_where_poll_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not hasattr(select, "poll"):
        pytest.skip("this platform has no poll")

    def no_select(*_args: Any) -> Any:
        raise ValueError("filedescriptor out of range in select()")

    monkeypatch.setattr(select, "select", no_select)
    backend = perplexity_agent._DeadlineBackend(time.monotonic() + 5.0, time.monotonic)
    left, right = socket.socketpair()
    stream = perplexity_agent._DeadlineStream(left, backend)
    try:
        assert stream.get_extra_info("is_readable") is False
        right.sendall(b"x")
        assert stream.get_extra_info("is_readable") is True
        left.recv(1)
        right.close()
        assert stream.get_extra_info("is_readable") is True
    finally:
        left.close()
        right.close()
