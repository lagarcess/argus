"""Retained document sources in a private Storage bucket.

Paths are ``{user_id}/{connection_id}/{sha256}``: owner-scoped, unguessable
through the random connection id, and named by their content, so writing the
same source twice leaves one object. Only the service role reaches the bucket;
owners read a source through the API, never through a signed URL.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol

SOURCE_BUCKET = "financial-document-sources"
_PAGE = 1000


def source_path(*, user_id: str, connection_id: str, sha256: str) -> str:
    return f"{user_id}/{connection_id}/{sha256}"


def connection_prefix(*, user_id: str, connection_id: str) -> str:
    return f"{user_id}/{connection_id}/"


def owner_prefix(user_id: str) -> str:
    return f"{user_id}/"


class SourceStorageUnavailable(RuntimeError):
    """Storage could not be reached or refused the call; retrying may succeed."""


def _require_folder(prefix: str) -> None:
    if not prefix.endswith("/"):
        raise ValueError("delete takes a folder prefix ending with /")


class SourceObjects(Protocol):
    bucket: str

    def put(self, path: str, content: bytes, media_type: str) -> None:
        """Write or overwrite one object."""
        ...

    def get(self, path: str) -> bytes | None:
        """The object's bytes, or None when it does not exist."""
        ...

    def delete(self, prefix: str) -> None:
        """Remove every object under ``prefix``, which ends with ``/``.
        Nothing there is not an error."""
        ...


class InMemorySourceObjects:
    bucket = SOURCE_BUCKET

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self._lock = threading.Lock()

    def put(self, path: str, content: bytes, media_type: str) -> None:
        with self._lock:
            self.objects[path] = content

    def get(self, path: str) -> bytes | None:
        with self._lock:
            return self.objects.get(path)

    def delete(self, prefix: str) -> None:
        _require_folder(prefix)
        with self._lock:
            for path in [path for path in self.objects if path.startswith(prefix)]:
                del self.objects[path]


class SupabaseSourceObjects:
    """Supabase Storage through the service-role client (``supabase.Client.storage``)."""

    bucket = SOURCE_BUCKET

    def __init__(self, storage: Any) -> None:
        self._bucket = storage.from_(self.bucket)

    def put(self, path: str, content: bytes, media_type: str) -> None:
        with _unavailable():
            self._bucket.upload(
                path, content, {"content-type": media_type, "upsert": "true"}
            )

    def get(self, path: str) -> bytes | None:
        from storage3.exceptions import StorageApiError

        with _unavailable():
            try:
                return self._bucket.download(path)
            except StorageApiError as error:
                if str(error.status) == "404":
                    return None
                raise

    def delete(self, prefix: str) -> None:
        _require_folder(prefix)
        with _unavailable():
            paths = self._paths(prefix)
            for start in range(0, len(paths), _PAGE):
                self._bucket.remove(paths[start : start + _PAGE])

    def _paths(self, prefix: str) -> list[str]:
        found: list[str] = []
        offset = 0
        while True:
            page = self._bucket.list(
                prefix.rstrip("/"), {"limit": _PAGE, "offset": offset}
            )
            for entry in page:
                path = f"{prefix}{entry['name']}"
                if entry.get("id") is None:
                    found += self._paths(f"{path}/")
                else:
                    found.append(path)
            if len(page) < _PAGE:
                return found
            offset += _PAGE


@contextmanager
def _unavailable() -> Iterator[None]:
    try:
        yield
    except Exception as error:
        raise SourceStorageUnavailable(type(error).__name__) from error
