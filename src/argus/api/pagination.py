from __future__ import annotations

import base64
import binascii

from fastapi import HTTPException, Request

from argus.api.dependencies import problem


def encode_cursor(timestamp: str, id: str) -> str:
    raw = f"{timestamp}|{id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def invalid_cursor_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=400,
        code="validation_error",
        title="Validation Error",
        detail="Invalid cursor.",
    )


def decode_cursor(cursor: str, request: Request) -> tuple[str, str]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        if "|" not in decoded:
            raise ValueError()
        timestamp, item_id = decoded.rsplit("|", 1)
        return timestamp, item_id
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise invalid_cursor_problem(request) from None


_encode_cursor = encode_cursor
_decode_cursor = decode_cursor
