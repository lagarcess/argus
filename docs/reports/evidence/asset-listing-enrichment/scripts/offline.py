"""Shared pieces of the offline checks: a fake network and a leak scan.

The fake network records each request and sends nothing. The leak scan reads a
file the way a person or a parser could: raw, with entities decoded, and with
tags removed or replaced by spaces. A check passes the declared tokens it wrote
on purpose, such as a ten-digit listing ID, as `allowed`.
"""

import html
import re
from pathlib import Path

from retention import CONTACT


class FakeResponse:
    def __init__(self, status, body, headers):
        self.status, self.body, self.headers = status, body, headers

    def read(self):
        return self.body


class FakeOpener:
    def __init__(self, pages):
        self.pages, self.calls = pages, []

    def open(self, request, timeout):
        self.calls.append(request.full_url)
        status, body, headers = self.pages.get(request.full_url, (404, b"", {}))
        return FakeResponse(status, body, headers)


def leaks(text, planted, allowed=()):
    decoded = html.unescape(text)
    views = [
        text,
        decoded,
        re.sub(r"<[^>]*>", "", decoded),
        re.sub(r"<[^>]*>", " ", decoded),
    ]
    found = {
        value for value in planted for view in views if value.lower() in view.lower()
    }
    found |= {
        match.group(0)
        for view in views
        for match in CONTACT.finditer(view)
        if match.group(0) not in allowed
    }
    return sorted(found)


def leaks_in_directory(root, planted, allowed=()):
    found = {}
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            hits = leaks(path.read_text("utf-8", "replace"), planted, allowed)
            if hits:
                found[str(path.relative_to(root))] = hits
    return found
