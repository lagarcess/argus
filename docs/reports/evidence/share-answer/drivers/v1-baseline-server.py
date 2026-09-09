"""Serve the previously committed public v1 JSON for a rendering comparison.

This transport fixture is only for the before/after browser baseline. Final
acceptance uses the application API and the isolated Supabase database.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
BODY = (
    ROOT
    / "docs/reports/evidence/receipt-sharing/2026-09-03-end-to-end/public-receipt.json"
).read_bytes()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(BODY)

    def do_POST(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:3319")
        self.end_headers()


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8319), Handler).serve_forever()
