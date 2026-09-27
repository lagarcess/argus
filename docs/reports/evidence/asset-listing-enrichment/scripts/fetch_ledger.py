#!/usr/bin/env python3
"""Budgeted, serial, cached page fetcher for the listing feasibility audit.

Stdlib only. Every network request is appended to ledger.jsonl before the
response is used. A URL already in the cache is replayed and never refetched.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path.cwd()
if (ROOT / ".git").exists() or "docs" in ROOT.parts:
    raise SystemExit("run from a scratch directory outside the repository")
CACHE = ROOT / "cache"
LEDGER = ROOT / "ledger.jsonl"
CLOCK = ROOT / "last_request.txt"

USER_AGENT = (
    "ArgusFeasibilityAudit/0.1 "
    "(one-time manual research sample; at most 20 requests per site; 4s spacing)"
)
SITES = {"supercarros": "supercarros.com", "supercasas": "supercasas.com"}
BUDGET_PER_SITE = 20
MIN_SPACING_S = 4.0
STOP_STATUSES = {401, 403, 407, 429, 503}
# Interstitial markers from common bot-management vendors. A contact-form
# reCAPTCHA on a normal page is only flagged, never treated as a wall.
WALL_MARKERS = (
    "cf-chl",
    "challenge-platform",
    "just a moment...",
    "attention required! | cloudflare",
    "pardon our interruption",
    "incapsula incident",
    "request unsuccessful",
    "px-captcha",
    "captcha-delivery.com",
    "are you a robot",
    "unusual traffic",
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def site_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    for key, domain in SITES.items():
        if host == domain or host.endswith("." + domain):
            return key
    raise SystemExit(f"refused: {host} is not an audited site")


def cache_paths(url: str) -> tuple[Path, Path]:
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    folder = CACHE / site_of(url)
    return folder / f"{key}.body", folder / f"{key}.json"


def ledger_rows(site: str) -> list[dict]:
    if not LEDGER.exists():
        return []
    rows = [json.loads(line) for line in LEDGER.read_text().splitlines() if line]
    return [row for row in rows if row["site"] == site]


def stop_file(site: str) -> Path:
    return ROOT / f"STOP_{site}.txt"


def robots_url(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def robots_verdict(url: str) -> tuple[bool, float | None, str]:
    target = robots_url(url)
    for _ in range(5):
        body_path, meta_path = cache_paths(target)
        if not meta_path.exists():
            return False, None, f"{target} not fetched yet"
        meta = json.loads(meta_path.read_text())
        if meta["status"] in (301, 302, 303, 307, 308) and meta["location"]:
            target = urllib.parse.urljoin(target, meta["location"])
            continue
        break
    status = meta["status"]
    if status in (404, 410):
        return True, None, f"robots.txt returned {status}; no rules"
    if status != 200:
        return False, None, f"robots.txt returned {status}; treated as disallow all"
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body_path.read_bytes().decode("utf-8", "replace").splitlines())
    allowed = parser.can_fetch(USER_AGENT, url)
    delay = parser.crawl_delay(USER_AGENT)
    return allowed, float(delay) if delay else None, "robots.txt parsed"


def decode(raw: bytes, encoding: str | None) -> bytes:
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        return zlib.decompress(raw)
    return raw


def wait_for_slot(spacing: float) -> None:
    if CLOCK.exists():
        elapsed = time.time() - float(CLOCK.read_text())
        if elapsed < spacing:
            time.sleep(spacing - elapsed)


def fetch(url: str, label: str) -> dict:
    site = site_of(url)
    body_path, meta_path = cache_paths(url)
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        return {**meta, "replayed_from_cache": True}
    if stop_file(site).exists():
        raise SystemExit(f"refused: {site} stopped: {stop_file(site).read_text()}")
    used = len(ledger_rows(site))
    if used >= BUDGET_PER_SITE:
        raise SystemExit(f"refused: {site} budget of {BUDGET_PER_SITE} used")

    spacing = MIN_SPACING_S
    robots_note = "robots.txt request"
    if label != "robots":
        allowed, delay, robots_note = robots_verdict(url)
        if not allowed:
            raise SystemExit(f"refused by robots gate: {robots_note}")
        if delay:
            spacing = max(spacing, delay)

    wait_for_slot(spacing)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.5",
            "Accept-Language": "es-DO,es;q=0.9,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    started = time.perf_counter()
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        response = OPENER.open(request, timeout=25)
        status, headers, raw = response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        status, headers, raw = error.code, error.headers, error.read()
    except (urllib.error.URLError, TimeoutError) as error:
        status, headers, raw = 0, {}, str(error).encode()
    elapsed_ms = round((time.perf_counter() - started) * 1000)
    CLOCK.write_text(str(time.time()))

    get = headers.get if hasattr(headers, "get") else (lambda *_: None)
    body = decode(raw, get("Content-Encoding"))
    lowered = body[:200_000].decode("utf-8", "replace").lower()
    wall = [marker for marker in WALL_MARKERS if marker in lowered]
    meta = {
        "site": site,
        "label": label,
        "url": url,
        "fetched_at": fetched_at,
        "status": status,
        "elapsed_ms": elapsed_ms,
        "bytes": len(body),
        "content_type": get("Content-Type"),
        "location": get("Location"),
        "server": get("Server"),
        "cache_control": get("Cache-Control"),
        "last_modified": get("Last-Modified"),
        "x_robots_tag": get("X-Robots-Tag"),
        "set_cookie_present": bool(get("Set-Cookie")),
        "wall_markers": wall,
        "captcha_mentions": lowered.count("captcha"),
        "robots_note": robots_note,
        "spacing_s": spacing,
    }
    with LEDGER.open("a") as ledger:
        ledger.write(json.dumps(meta) + "\n")
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_bytes(body)
    meta_path.write_text(json.dumps(meta, indent=2))

    if status in STOP_STATUSES or wall:
        stop_file(site).write_text(
            f"{fetched_at} status={status} markers={wall} url={url}"
        )
        meta["stopped_site"] = True
    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    meta = fetch(args.url, args.label)
    json.dump(meta, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
