import http.client
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest
from financial_response_fault import Fault, handler


@contextmanager
def running(handler_type):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_type)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize(
    "method,path,status",
    [
        ("POST", "/api/v1/financial-activities/preview", 200),
        ("POST", "/api/v1/financial-activities", 409),
        ("GET", "/api/v1/financial-activities/entry", 200),
        ("POST", "/api/v1/auth/login", 200),
        ("POST", "/api/v1/financial-plan/occurrences/example/link/preview", 200),
        ("PUT", "/api/v1/financial-plan/selection", 409),
        ("GET", "/api/v1/financial-plan/expectations", 200),
    ],
)
def test_fault_ignores_reads_previews_and_failed_writes(method, path, status):
    fault = Fault()
    fault.arm()
    assert not fault.consume(method, path, status)
    assert fault.armed and fault.dropped == 0


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/api/v1/financial-activities"),
        ("POST", "/api/v1/financial-plan/expectations"),
        ("PATCH", "/api/v1/financial-plan/expectations/example"),
        ("PUT", "/api/v1/financial-plan/selection"),
        ("POST", "/api/v1/financial-plan/occurrences/example/fulfillment"),
        ("POST", "/api/v1/financial-plan/occurrences/example/link"),
    ],
)
def test_response_is_lost_only_after_upstream_accepts_the_write(method, path):
    accepted = []

    class API(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            accepted.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(201)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

    API.do_PATCH = API.do_POST
    API.do_PUT = API.do_POST
    fault = Fault()
    with running(API) as upstream, running(handler(upstream, fault)) as proxy:
        client = http.client.HTTPConnection("127.0.0.1", proxy, timeout=3)
        client.request("POST", "/__fault")
        assert client.getresponse().read() == b'{"armed": true, "dropped": 0}'
        client.request(method, path, b'{"amount":"10"}')
        with pytest.raises(http.client.RemoteDisconnected):
            client.getresponse()
        assert accepted == [b'{"amount":"10"}']
        client.request(method, path, b'{"amount":"10"}')
        response = client.getresponse()
        assert response.status == 201 and response.read() == b"{}"
        assert fault.dropped == 1 and not fault.armed
        client.close()
