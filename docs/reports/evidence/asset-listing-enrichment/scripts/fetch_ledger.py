#!/usr/bin/env python3
"""Budgeted, serial, cached page fetcher for the listing feasibility audit.

Stdlib only. The URL alone decides the page kind and the robots check. Every
network request is appended to ledger.jsonl, and only what retention.retain
keeps reaches the cache. A URL already in the cache is replayed and never
refetched.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from retention import DETAIL_PATH, retain

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


def study_root() -> Path:
    root = Path.cwd()
    if (root / ".git").exists() or "docs" in root.parts:
        raise SystemExit("run from a scratch directory outside the repository")
    return root


def site_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    for key, domain in SITES.items():
        if host == domain or host.endswith("." + domain):
            return key
    raise SystemExit(f"refused: {host} is not an audited site")


def classify(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    try:
        port = parts.port
    except ValueError:
        port = -1
    if (
        parts.scheme != "https"
        or parts.username
        or parts.password
        or port is not None
        or parts.fragment
    ):
        raise SystemExit(f"refused: {url} is not a plain https URL")
    site = site_of(url)
    path, query = parts.path, parts.query
    if path == "/robots.txt" and not query:
        return site, "robots"
    if path == "/sitemap.xml" and not query:
        return site, "sitemap"
    if path == "/assets/js/searchvalues.js" and re.fullmatch(r"\d*", query):
        return site, "search-values"
    if DETAIL_PATH.fullmatch(path) and not query:
        return site, "detail"
    raise SystemExit(f"refused: {url} is not a URL shape this fetcher may request")


def cache_paths(url: str) -> tuple[Path, Path]:
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    folder = study_root() / "cache" / site_of(url)
    return folder / f"{key}.body", folder / f"{key}.json"


def ledger_rows(site: str) -> list[dict]:
    ledger = study_root() / "ledger.jsonl"
    if not ledger.exists():
        return []
    rows = [json.loads(line) for line in ledger.read_text().splitlines() if line]
    return [row for row in rows if row["site"] == site]


def stop_file(site: str) -> Path:
    return study_root() / f"STOP_{site}.txt"


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
    if status != 200 or not body_path.exists():
        return False, None, f"robots.txt returned {status} or was not kept; disallow all"
    rules = body_path.read_bytes().decode("utf-8", "replace")
    strict, folded = (
        urllib.robotparser.RobotFileParser(),
        urllib.robotparser.RobotFileParser(),
    )
    strict.parse(rules.splitlines())
    folded.parse(rules.lower().splitlines())
    parts = urlsplit(url)
    lowered = urlunsplit(parts._replace(path=parts.path.lower()))
    allowed = strict.can_fetch(USER_AGENT, url) and folded.can_fetch(USER_AGENT, lowered)
    delay = strict.crawl_delay(USER_AGENT)
    return allowed, float(delay) if delay else None, "robots.txt parsed"


def decode(raw: bytes, encoding: str | None) -> bytes:
    if encoding == "gzip":
        return gzip.decompress(raw)
    if encoding == "deflate":
        return zlib.decompress(raw)
    return raw


def wait_for_slot(spacing: float) -> None:
    clock = study_root() / "last_request.txt"
    if clock.exists():
        elapsed = time.time() - datetime.fromisoformat(clock.read_text()).timestamp()
        if elapsed < spacing:
            time.sleep(spacing - elapsed)


def fetch(url: str) -> dict:
    site, kind = classify(url)
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
    if kind != "robots":
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
    (study_root() / "last_request.txt").write_text(datetime.now(timezone.utc).isoformat())

    get = headers.get if hasattr(headers, "get") else (lambda *_: None)
    body = decode(raw, get("Content-Encoding"))
    lowered = body[:200_000].decode("utf-8", "replace").lower()
    wall = [marker for marker in WALL_MARKERS if marker in lowered]
    kept, retention = retain(kind, status, body)
    meta = {
        "site": site,
        "label": kind,
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
        "retention": retention,
        "kept_bytes": len(kept) if kept else 0,
    }
    with (study_root() / "ledger.jsonl").open("a") as ledger:
        ledger.write(json.dumps(meta) + "\n")
    body_path.parent.mkdir(parents=True, exist_ok=True)
    if kept:
        body_path.write_bytes(kept)
    meta_path.write_text(json.dumps(meta, indent=2))

    if status in STOP_STATUSES or wall:
        stop_file(site).write_text(
            f"{fetched_at} status={status} markers={wall} url={url}"
        )
        meta["stopped_site"] = True
    return meta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args(argv)
    meta = fetch(args.url)
    json.dump(meta, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
