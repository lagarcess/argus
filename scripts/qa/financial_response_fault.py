"""Drop a successful local financial write response to exercise native recovery."""

from __future__ import annotations

import argparse
import http.client
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import urlsplit


class Fault:
    def __init__(self) -> None:
        self.lock = Lock()
        self.armed = False
        self.dropped = 0

    def arm(self) -> None:
        with self.lock:
            self.armed = True

    def consume(self, method: str, path: str, status: int) -> bool:
        eligible = (
            method in {"POST", "PATCH"}
            and path.startswith("/api/v1/financial-activities")
            and not path.endswith("/preview")
            and 200 <= status < 300
        )
        with self.lock:
            if not self.armed or not eligible:
                return False
            self.armed = False
            self.dropped += 1
            return True


def handler(upstream_port: int, fault: Fault) -> type[BaseHTTPRequestHandler]:
    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def forward(self) -> None:
            if self.path == "/__fault":
                if self.command == "POST":
                    fault.arm()
                with fault.lock:
                    payload = json.dumps(
                        {"armed": fault.armed, "dropped": fault.dropped}
                    ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if not self.path.startswith("/api/v1/"):
                self.send_error(404)
                return
            content = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            excluded = {"host", "connection", "transfer-encoding", "content-length"}
            headers = {k: v for k, v in self.headers.items() if k.lower() not in excluded}
            upstream = http.client.HTTPConnection("127.0.0.1", upstream_port, timeout=45)
            try:
                upstream.request(self.command, self.path, content, headers)
                response = upstream.getresponse()
                body = response.read()
                if fault.consume(self.command, urlsplit(self.path).path, response.status):
                    self.close_connection = True
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                self.send_response(response.status)
                for key, value in response.getheaders():
                    if key.lower() not in excluded:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (ConnectionError, TimeoutError):
                self.close_connection = True
            finally:
                upstream.close()

        do_GET = forward
        do_POST = forward
        do_PATCH = forward
        do_DELETE = forward

    return Proxy


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listen-port", type=int, default=58512)
    parser.add_argument("--upstream-port", type=int, default=58500)
    args = parser.parse_args()
    if args.listen_port == args.upstream_port:
        parser.error("The proxy and API need different ports.")
    ThreadingHTTPServer(
        ("127.0.0.1", args.listen_port), handler(args.upstream_port, Fault())
    ).serve_forever()
