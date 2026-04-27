from unittest.mock import MagicMock

import pytest
from argus.api.main import _decode_cursor, _encode_cursor
from fastapi import Request
from fastapi.exceptions import HTTPException


def test_cursor_roundtrip():
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.request_id = "req-1"

    timestamp = "2024-01-01T12:00:00Z"
    item_id = "test-id"

    encoded = _encode_cursor(timestamp, item_id)
    assert encoded != timestamp
    assert encoded != item_id

    dec_ts, dec_id = _decode_cursor(encoded, request)
    assert dec_ts == timestamp
    assert dec_id == item_id


def test_invalid_cursor():
    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.request_id = "req-1"

    # Must use pytest.raises with HTTPException
    with pytest.raises(HTTPException):
        _decode_cursor("not base64", request)

    import base64

    invalid_format = base64.urlsafe_b64encode(b"just a string").decode("ascii")
    with pytest.raises(HTTPException):
        _decode_cursor(invalid_format, request)
