"""Pure bounded delimited-text intake. File cells are data, never executable text."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from .common import PlatformError

PARSER_VERSION = "delimited-v1"


@dataclass(frozen=True)
class ParserLimits:
    max_bytes: int = 1_000_000
    max_rows: int = 2_000
    max_columns: int = 64
    max_cell_chars: int = 4_096
    max_header_row: int = 50


DEFAULT_LIMITS = ParserLimits()


@dataclass(frozen=True)
class DelimitedRow:
    line: int
    cells: tuple[str, ...]


@dataclass(frozen=True)
class DelimitedTable:
    headers: tuple[str, ...]
    rows: tuple[DelimitedRow, ...]
    file_digest: str


def _check_quotes(content: str, delimiter: str) -> None:
    # csv.reader(strict=True) accepts a quote embedded in an unquoted field.
    # Reject that ambiguity before the standard parser reads logical records.
    state = "start"
    for character in content:
        if state == "quoted":
            if character == '"':
                state = "closed"
        elif state == "closed":
            if character == '"':
                state = "quoted"
            elif character == delimiter or character in "\r\n":
                state = "start"
            else:
                raise PlatformError("invalid_csv_quoting")
        elif character == '"':
            if state != "start":
                raise PlatformError("invalid_csv_quoting")
            state = "quoted"
        elif character == delimiter or character in "\r\n":
            state = "start"
        else:
            state = "unquoted"
    if state == "quoted":
        raise PlatformError("invalid_csv_quoting")


def parse_delimited(
    content: str,
    *,
    delimiter: str = ",",
    header_row: int = 1,
    limits: ParserLimits = DEFAULT_LIMITS,
) -> DelimitedTable:
    """Count every logical record, including invalid/blank rows, before mapping."""
    try:
        encoded = content.encode("utf-8")
    except UnicodeEncodeError:
        raise PlatformError("invalid_file_encoding") from None
    if len(encoded) > limits.max_bytes:
        raise PlatformError("import_too_large")
    if delimiter not in (",", ";", "\t") or not 1 <= header_row <= limits.max_header_row:
        raise PlatformError("invalid_import_format")
    if any(
        (ord(c) < 32 and c not in "\t\r\n") or 127 <= ord(c) <= 159 or c == "\ufffd"
        for c in content
    ):
        raise PlatformError("invalid_file_content")
    normalized = content.removeprefix("\ufeff")
    _check_quotes(normalized, delimiter)
    reader = csv.reader(
        io.StringIO(normalized, newline=""), delimiter=delimiter, strict=True
    )
    rows: list[DelimitedRow] = []
    headers: tuple[str, ...] | None = None
    try:
        for index, cells in enumerate(reader, 1):
            if index > header_row + limits.max_rows:
                raise PlatformError("import_too_many_rows")
            if len(cells) > limits.max_columns:
                raise PlatformError("import_too_many_columns")
            if any(len(cell) > limits.max_cell_chars for cell in cells):
                raise PlatformError("import_cell_too_large")
            if index < header_row:
                continue
            if index == header_row:
                headers = tuple(cell.strip() for cell in cells)
                if (
                    not headers
                    or any(not header for header in headers)
                    or len(set(headers)) != len(headers)
                ):
                    raise PlatformError("invalid_csv_headers")
            else:
                rows.append(DelimitedRow(reader.line_num, tuple(cells)))
    except csv.Error:
        raise PlatformError("invalid_csv") from None
    if headers is None:
        raise PlatformError("invalid_csv_headers")
    return DelimitedTable(headers, tuple(rows), hashlib.sha256(encoded).hexdigest())


def statement_amount(value: str, decimal_separator: str) -> Decimal:
    value = value.strip()
    separator = re.escape(decimal_separator)
    # No exponent, grouping guesses, expressions or locale-dependent float parse.
    if not re.fullmatch(rf"[+-]?[0-9]+(?:{separator}[0-9]+)?", value):
        raise PlatformError("invalid_statement_amount")
    return Decimal(value.replace(decimal_separator, "."))


def statement_date(value: str, date_format: str) -> str:
    patterns = {"YMD": "%Y-%m-%d", "DMY": "%d/%m/%Y", "MDY": "%m/%d/%Y"}
    try:
        return datetime.strptime(value.strip(), patterns[date_format]).date().isoformat()
    except (ValueError, KeyError):
        raise PlatformError("invalid_statement_date") from None
