"""Validate exact quoted occurrences against individually named run facts.

References establish value, unit and occurrence truth, not arbitrary prose
entailment. Cardinal words use number-parser; dates use the shared locale data.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from babel.dates import get_month_names
from dateparser.date import DateDataParser
from number_parser import parse, parse_number

from argus.domain.result_readout_fact_sheet import resolve_readout_fact


def _fold(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c)
    )


_NUMBER = re.compile(
    r"(?<!\d)[-+−]?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?!\d)(?:[.,]\d+)?"
    r"|(?:\d+(?:[.,]\d+)*|[.,]\d+))(?:[eE][+-]?\d+|[kKmMbB](?!\w))?"
)


def _number(token: str, *, money: bool = False) -> tuple[float, int]:
    token = re.sub(r"[ \u00a0\u202f]", "", token.replace("−", "-"))
    suffix = re.search(r"([eE][+-]?\d+|[kKmMbB])$", token)
    exponent = 0
    if suffix:
        scale = suffix.group()
        exponent = (
            int(scale[1:])
            if scale[0].lower() == "e"
            else {"k": 3, "m": 6, "b": 9}[scale.lower()]
        )
        token = token[: suffix.start()]
    if "." in token and "," in token:
        decimal = "." if token.rfind(".") > token.rfind(",") else ","
        token = token.replace("," if decimal == "." else ".", "").replace(decimal, ".")
    elif "," in token or "." in token:
        separator = "," if "," in token else "."
        pieces = token.split(separator)
        # A leading zero cannot be a thousands group (e.g. Sharpe 0.456).
        grouped = (
            ((money and separator == ",") or len(pieces) > 2)
            and pieces[0].lstrip("+-") != "0"
            and all(len(p) == 3 for p in pieces[1:])
        )
        token = "".join(pieces) if grouped else token.replace(separator, ".")
    decimals = len(token.rsplit(".", 1)[1]) if "." in token else 0
    try:
        return float(f"{token}e{exponent}"), decimals - exponent
    except ValueError:
        return math.nan, decimals


_CURRENCIES = {
    "USD": r"\$|\bUSD\b|\bdollars?\b|\bdolares?\b",
    "EUR": r"€|\bEUR\b|\beuros?\b",
    "GBP": r"£|\bGBP\b|\bpounds?\b|\blibras?\b",
}
_CURRENCY_TOKENS = "(?:" + "|".join(_CURRENCIES.values()) + ")"


def _quoted_currency(before: str, after: str) -> str | None:
    for code, tokens in _CURRENCIES.items():
        if re.search(r"(?:" + tokens + r")\s*$", before, re.I) or re.match(
            r"\s*(?:" + tokens + ")", after, re.I
        ):
            return code
    return None


_QUOTED_UNITS = {
    "currency": re.compile(
        _CURRENCY_TOKENS + r"|\b(?:capital|profit|balance|saldo|contribucion)\b",
        re.I,
    ),
    "ratio": re.compile(r"\b(?:sharpe|ratio|profit factor|factor de beneficio)\b", re.I),
    "count": re.compile(
        r"\b(?:fills?|trades?|operations?|operacion(?:es)?|periods?|periodos?|days?|dias?|shares?|acciones)\b",
        re.I,
    ),
    "percent": re.compile(
        r"\b(?:return|rendimiento|volatility|volatilidad|drawdown|caida)\b", re.I
    ),
}
_PERCENT_SUFFIX = re.compile(
    r"^\s*(?:%|percent\b|por ciento\b)",
    re.I,
)
_POINTS_SUFFIX = re.compile(
    r"^\s*(?:percentage points?\b|puntos? porcentuales?\b|pp\b|pts\b)", re.I
)
_BASIS_SUFFIX = re.compile(r"^\s*(?:bps\b|basis points?\b|puntos? basicos?\b)", re.I)


def _quoted_unit(text: str, match: re.Match[str]) -> str:
    before, after = _fold(text[: match.start()]), _fold(text[match.end() :])
    if _POINTS_SUFFIX.match(after):
        return "percentage_points"
    if _PERCENT_SUFFIX.match(after):
        return "percent"
    if _BASIS_SUFFIX.match(after):
        return "basis_points"
    if _quoted_currency(before, after):
        return "currency"
    if _QUOTED_UNITS["count"].match(after.lstrip()) or re.match(
        r"^\s*\w+\s+" + _QUOTED_UNITS["count"].pattern, after, re.I
    ):
        return "count"
    if re.match(r"\s*x\b", after):
        return "ratio"
    if any(
        date.start() <= match.start() < date.end()
        for date in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", text)
    ):
        return "date"
    # The nearest preceding unit label supplies the unit for a bare figure.
    # Stop at another figure so one metric's label cannot color the next one.
    previous = list(_NUMBER.finditer(before))
    local = before[previous[-1].end() :] if previous else before
    labels = [
        (label.start(), unit)
        for unit, pattern in _QUOTED_UNITS.items()
        for label in pattern.finditer(local)
        # Count labels must attach locally, allowing a linking word, instead
        # of spanning unrelated prose such as a following natural date.
        if unit != "count"
        or re.fullmatch(r"\s*[:=()]?\s*(?:\w+\s*)?", local[label.end() :])
    ]
    return max(labels)[1] if labels else "scalar"


@dataclass(frozen=True)
class _FigureSpan:
    start: int
    end: int
    numeric: str
    date: bool = False


def _word_numbers(text: str, language: str) -> tuple[str, list[tuple[int, int]]]:
    """Retain raw offsets while the library converts supported cardinal phrases."""
    # Unit phrases (notably Spanish "por ciento") contain numeral words but
    # denote a unit. Derive protected spans from the same unit grammar.
    unit_pattern = re.compile(
        "|".join(
            pattern.pattern.removeprefix(r"^\s*")
            for pattern in (_PERCENT_SUFFIX, _POINTS_SUFFIX, _BASIS_SUFFIX)
        ),
        re.I,
    )
    pieces: list[str] = []
    cursor = 0
    for unit in unit_pattern.finditer(text):
        pieces.extend(
            (parse(text[cursor : unit.start()], language=language), unit.group())
        )
        cursor = unit.end()
    pieces.append(parse(text[cursor:], language=language))
    converted = "".join(pieces)
    offsets: list[tuple[int, int]] = []
    for kind, first, last, new_first, new_last in SequenceMatcher(
        None, text, converted, autojunk=False
    ).get_opcodes():
        if kind == "equal":
            offsets.extend((i, i + 1) for i in range(first, last))
        else:
            offsets.extend((first, last) for _ in range(new_first, new_last))
    return converted, offsets


@lru_cache(maxsize=2)
def _date_pattern(language: str) -> re.Pattern[str]:
    months = {
        name.rstrip(".")
        for width in ("wide", "abbreviated")
        for name in get_month_names(width, locale=language).values()
    }
    month = (
        "(?:"
        + "|".join(re.escape(name) for name in sorted(months, key=len, reverse=True))
        + r")\.?"
    )
    return re.compile(
        r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?\b"
        + r"|\b\d{1,2}\s+(?:de\s+)?"
        + month
        + r"(?:\s+(?:de\s+)?\d{4})?\b"
        + r"|\b"
        + month
        + r"[,\s]*(?:[^\W\d_]+[,\s]+)?(?:\d{1,2}(?:st|nd|rd|th)?[,]?\s+)?\d{4}\b",
        re.I,
    )


def _visible_figures(
    text: str, language: str, facts: dict[str, Any]
) -> list[_FigureSpan]:
    converted, offsets = _word_numbers(text, language)
    figures: list[_FigureSpan] = []
    # A narrowly recognized instrument name is a lexical token, never a value.
    identities = [*(facts.get("symbols") or []), facts.get("benchmark_symbol")]
    names = (
        list(re.finditer(r"\bS\s*&\s*P\s*500\b(?!\s*[%$€£])", converted, re.I))
        if "SPY" in identities
        else []
    )
    dates = list(_date_pattern(language).finditer(converted))
    for match in dates:
        figures.append(
            _FigureSpan(
                offsets[match.start()][0],
                offsets[match.end() - 1][1],
                match.group(),
                True,
            )
        )
    for match in _NUMBER.finditer(converted):
        if any(span.start() <= match.start() < span.end() for span in (*names, *dates)):
            continue
        start, end = offsets[match.start()][0], offsets[match.end() - 1][1]
        raw = text[start:end]
        if raw != match.group():
            # The parser also converts indefinite articles and ordinal discourse.
            # A cardinal one is a quote only in numerical context; other cardinal
            # phrases are figures. Unsupported word forms remain outside this check.
            cardinal = parse_number(raw, language=language)
            if cardinal is None or (
                cardinal == 1 and _quoted_unit(converted, match) == "scalar"
            ):
                continue
        prefix = converted[: match.start()].rsplit("\n", 1)[-1]
        if not prefix.strip() and converted[match.end() : match.end() + 2] in {
            ". ",
            ") ",
        }:
            continue
        figures.append(_FigureSpan(start, end, match.group()))
    return sorted(figures, key=lambda span: span.start)


def _finite(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _date_matches(quote: str, canonical: object, language: str) -> bool:
    if not isinstance(canonical, str):
        return False
    try:
        expected = datetime.fromisoformat(canonical.replace("Z", "+00:00"))
    except ValueError:
        return False
    quoted = DateDataParser(
        languages=[language], settings={"RELATIVE_BASE": expected}
    ).get_date_data(quote)
    date = quoted.date_obj
    if date is None:
        return False
    if re.fullmatch(r"\d{4}", quote):
        return date.year == expected.year
    if re.fullmatch(r"\d{1,2}", quote):
        return date.day == expected.day
    if quoted.period == "month":
        return (date.year, date.month) == (expected.year, expected.month)
    if "T" in quote:
        return date == expected
    return date.date() == expected.date()


def _matches_row(
    text: str, span: _FigureSpan, row: dict[str, Any], language: str
) -> bool:
    unit = row.get("unit")
    value = row.get("value")
    if unit in {"date", "timestamp"}:
        # Explicit monetary/count/ratio units cannot be excused by a date component.
        match = _NUMBER.search(span.numeric)
        if not span.date and match:
            contextual = _quoted_unit(
                text[: span.start] + span.numeric + text[span.end :],
                next(
                    _NUMBER.finditer(
                        text[: span.start] + span.numeric + text[span.end :], span.start
                    )
                ),
            )
            if contextual != "scalar":
                return False
        return _date_matches(span.numeric, value, language)
    if span.date or not _finite(value):
        return False
    numeric_text = text[: span.start] + span.numeric + text[span.end :]
    match = _NUMBER.match(numeric_text, span.start)
    if match is None:
        return False
    quoted_unit = _quoted_unit(numeric_text, match)
    if quoted_unit == "currency" and row.get("currency"):
        currency = _quoted_currency(
            _fold(numeric_text[: match.start()]), _fold(numeric_text[match.end() :])
        )
        if currency and currency != row["currency"]:
            return False
    number, decimals = _number(span.numeric, money=quoted_unit == "currency")
    if not math.isfinite(number):
        return False
    presentation = row.get("presentation") or []
    if quoted_unit == "scalar":
        compatible = unit in {"count", "ratio", "indicator_points"}
    else:
        compatible = unit == quoted_unit
    if quoted_unit == "percent" and "fraction_as_percent" in presentation:
        value, compatible = value * 100, True
    if (
        quoted_unit == "percentage_points"
        and "basis_points_as_percentage_points" in presentation
    ):
        value, compatible = value / 100, True
    if "absolute_magnitude" in presentation and not span.numeric.startswith(
        ("+", "-", "−")
    ):
        value = abs(value)
    try:
        tolerance = float(f"5e{-decimals - 1}") + 1e-8
    except (OverflowError, ValueError):
        return False
    return compatible and abs(number - value) <= tolerance


def validate_figure_references(
    text: str,
    references: list[dict[str, Any]],
    *,
    facts: dict[str, Any],
    language: str,
    source_references: tuple[tuple[dict[str, Any], dict[str, Any]], ...] = (),
    source_citation_spans: tuple[tuple[int, int], ...] = (),
) -> str | None:
    """Check canonical keys/values and complete coverage before text normalization."""
    locale = "es" if language == "es-419" else "en"
    visible = _visible_figures(text, locale, facts)
    covered: set[int] = set()
    occupied: list[tuple[int, int]] = []
    cited_run_figure = False
    # A web citation may authorize its own figure, never a lookup in run facts.
    resolved = [(ref, resolve_readout_fact(facts, ref["fact_key"])) for ref in references]
    for reference_index, (reference, row) in enumerate([*resolved, *source_references]):
        if not row or row.get("unit") in {"unknown", "text", "boolean"}:
            return "invalid_figure_reference"
        value = row.get("value")
        quoted_value = reference["value"]
        if value is None or isinstance(value, bool) or quoted_value != value:
            return "invalid_figure_reference"
        if not isinstance(value, str) and not (_finite(value) and _finite(quoted_value)):
            return "invalid_figure_reference"
        occurrences = list(re.finditer(re.escape(reference["quote"]), text))
        occurrence = reference["occurrence"]
        if occurrence > len(occurrences):
            return "invalid_figure_reference"
        quote = occurrences[occurrence - 1]
        if any(start < quote.end() and quote.start() < end for start, end in occupied):
            return "invalid_figure_reference"
        attached = [
            (index, span)
            for index, span in enumerate(visible)
            if quote.start() <= span.start and span.end <= quote.end()
        ]
        if len(attached) != 1:
            return "invalid_figure_reference"
        index, span = attached[0]
        if index in covered or not _matches_row(text, span, row, locale):
            return "invalid_figure_reference"
        if reference_index < len(resolved):
            cited_run_figure |= any(
                start < span.end and span.start < end
                for start, end in source_citation_spans
            )
        occupied.append(quote.span())
        covered.add(index)
    if len(covered) != len(visible):
        return "unreferenced_figure"
    return "invalid_source_reference" if cited_run_figure else None
