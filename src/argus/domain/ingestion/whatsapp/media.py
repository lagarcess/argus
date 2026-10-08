"""Bounded media download from Meta's trusted hosts.

1. ``GET https://graph.facebook.com/{version}/{media-id}`` returns a short-lived
   URL, the MIME type and the size. Only the Graph host is ever asked.
2. The URL is fetched only when it is HTTPS on an allowlisted Meta CDN host,
   with the bearer token, no redirects, a Content-Length check and a streaming
   cap. A URL that 404s once is re-requested once, since it lives 5 minutes.

A 404 or 410 from either step means the media is gone: ``MediaUnavailable``
with ``expired=True``. The person can send it again.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

GRAPH_HOST = "graph.facebook.com"
DOWNLOAD_HOSTS = frozenset({"lookaside.fbsbx.com"})
DOWNLOAD_HOST_SUFFIXES = (".fbcdn.net",)
ACCEPTED_MEDIA_TYPES = frozenset({"application/pdf", "image/jpeg", "image/png"})
_GONE = frozenset({404, 410})
_TIMEOUT = httpx.Timeout(10.0)
_META_HOSTS = (GRAPH_HOST, *DOWNLOAD_HOSTS, *DOWNLOAD_HOST_SUFFIXES)


class _DropMetaRequestLines(logging.Filter):
    """httpx logs each request URL at INFO; Meta URLs carry media ids."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(host in message for host in _META_HOSTS)


_httpx_logger = logging.getLogger("httpx")
if not any(isinstance(f, _DropMetaRequestLines) for f in _httpx_logger.filters):
    _httpx_logger.addFilter(_DropMetaRequestLines())


class MediaRejected(Exception):
    """The media can never be captured: wrong type or too large."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class MediaUnavailable(Exception):
    """The media could not be fetched now; sending it again can succeed."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FetchedMedia:
    content: bytes
    mime_type: str


def trusted_download_url(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return (
        parts.scheme == "https"
        and parts.port is None
        and not parts.username
        and not parts.password
        and (host in DOWNLOAD_HOSTS or host.endswith(DOWNLOAD_HOST_SUFFIXES))
    )


class GraphMedia:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        access_token: str,
        graph_api_version: str,
        max_bytes: int,
    ) -> None:
        self._client = client
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._version = graph_api_version
        self._max_bytes = max_bytes

    async def fetch(self, media_id: str) -> FetchedMedia:
        if not media_id.isascii() or not media_id.isdigit():
            raise MediaUnavailable("whatsapp_media_unavailable")
        for _ in range(2):
            url, mime_type = await self._locate(media_id)
            content = await self._download(url)
            if content is not None:
                return FetchedMedia(content, mime_type)
        raise MediaUnavailable("whatsapp_media_expired")

    async def _locate(self, media_id: str) -> tuple[str, str]:
        try:
            response = await self._client.get(
                f"https://{GRAPH_HOST}/{self._version}/{media_id}",
                headers=self._headers,
                timeout=_TIMEOUT,
                follow_redirects=False,
            )
        except httpx.HTTPError:
            raise MediaUnavailable("whatsapp_media_unavailable") from None
        if response.status_code in _GONE:
            raise MediaUnavailable("whatsapp_media_expired")
        if response.status_code != 200:
            raise MediaUnavailable("whatsapp_media_unavailable")
        try:
            meta = response.json()
            url, mime_type = str(meta["url"]), str(meta["mime_type"])
            size = int(meta.get("file_size") or 0)
        except (ValueError, KeyError, TypeError):
            raise MediaUnavailable("whatsapp_media_unavailable") from None
        mime_type = mime_type.split(";", 1)[0].strip().lower()
        if mime_type not in ACCEPTED_MEDIA_TYPES:
            raise MediaRejected("whatsapp_media_unsupported")
        if size > self._max_bytes:
            raise MediaRejected("whatsapp_media_too_large")
        if not trusted_download_url(url):
            raise MediaUnavailable("whatsapp_media_untrusted")
        return url, mime_type

    async def _download(self, url: str) -> bytes | None:
        """The bytes, or ``None`` when the short-lived URL has already expired."""

        try:
            async with self._client.stream(
                "GET",
                url,
                headers=self._headers,
                timeout=_TIMEOUT,
                follow_redirects=False,
            ) as response:
                if response.status_code in _GONE:
                    return None
                if response.status_code != 200:
                    raise MediaUnavailable("whatsapp_media_unavailable")
                declared = response.headers.get("content-length")
                if declared is not None and (
                    not declared.isdigit() or int(declared) > self._max_bytes
                ):
                    raise MediaRejected("whatsapp_media_too_large")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self._max_bytes:
                        raise MediaRejected("whatsapp_media_too_large")
                return bytes(content)
        except httpx.HTTPError:
            raise MediaUnavailable("whatsapp_media_unavailable") from None
