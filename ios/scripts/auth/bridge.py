"""Serve only the lane's public CAPTCHA test page on loopback; never log tokens."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if urlsplit(self.path).path != "/captcha.html":
            self.send_error(404)
            return
        mode_file = Path(__file__).resolve().parents[2] / ".build/auth-local/captcha-mode"
        mode = mode_file.read_text().strip() if mode_file.exists() else "pass"
        if mode not in {"pass", "fail", "hold"}:
            self.send_error(503)
            return
        body = (
            Path(__file__)
            .with_name("captcha.html")
            .read_text()
            .replace("LOCAL_TEST_MODE", mode)
            .encode()
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 58405), Handler).serve_forever()
