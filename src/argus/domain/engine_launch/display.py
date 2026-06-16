from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from babel.dates import format_date as format_locale_date

Language = Literal["en", "es-419"]
TimeframeUnit = Literal["minute", "hour", "day", "week"]


@dataclass(frozen=True)
class TimeframeDisplay:
    raw: str
    amount: int | None
    unit: TimeframeUnit | None
    language: Language
    data_label: str
    recurring_price_label: str


_TIMEFRAME_ALIASES: dict[str, tuple[int, TimeframeUnit]] = {
    "m": (1, "minute"),
    "min": (1, "minute"),
    "minute": (1, "minute"),
    "minutes": (1, "minute"),
    "h": (1, "hour"),
    "hour": (1, "hour"),
    "hourly": (1, "hour"),
    "d": (1, "day"),
    "day": (1, "day"),
    "daily": (1, "day"),
    "w": (1, "week"),
    "week": (1, "week"),
    "weekly": (1, "week"),
}
_UNIT_ALIASES: dict[str, TimeframeUnit] = {
    "m": "minute",
    "min": "minute",
    "mins": "minute",
    "minute": "minute",
    "minutes": "minute",
    "h": "hour",
    "hr": "hour",
    "hrs": "hour",
    "hour": "hour",
    "hours": "hour",
    "d": "day",
    "day": "day",
    "days": "day",
    "w": "week",
    "wk": "week",
    "wks": "week",
    "week": "week",
    "weeks": "week",
}


def format_timeframe_data_label(
    timeframe: object,
    *,
    language: str = "en",
) -> str:
    return describe_timeframe(timeframe, language=language).data_label


def format_data_through_label(value: object, *, language: str = "en") -> str:
    parsed = _parse_date(value)
    if parsed is None:
        return ""
    if _resolve_language(language) == "es-419":
        return f"Hasta {_spanish_short_month_day(parsed)}"
    return f"Through {_english_short_month_day(parsed)}"


def format_date_label(value: object, *, language: str = "en") -> str:
    parsed = _parse_date(value)
    if parsed is None:
        return str(value or "").strip()
    return format_locale_date(
        parsed,
        format="long",
        locale=_locale_identifier(language),
    )


def format_date_range_label(
    start: object,
    end: object,
    *,
    language: str = "en",
    separator: str | None = None,
) -> str:
    start_label = format_date_label(start, language=language)
    end_label = format_date_label(end, language=language)
    if not start_label or not end_label:
        return ""
    if separator is None:
        separator = " al " if _resolve_language(language) == "es-419" else " - "
    return f"{start_label}{separator}{end_label}"


def format_timeframe_data_caveat(
    timeframe: object,
    *,
    language: str = "en",
) -> str:
    display = describe_timeframe(timeframe, language=language)
    if display.language == "es-419":
        return f"Solo {_lower_initial(display.data_label)}."
    return f"{display.data_label} only."


def format_recurring_entry_caveat(
    timeframe: object,
    *,
    language: str = "en",
) -> str:
    display = describe_timeframe(timeframe, language=language)
    if display.language == "es-419":
        return (
            "Las entradas recurrentes usan el primer precio "
            f"{display.recurring_price_label} disponible en cada ventana de cadencia."
        )
    return (
        "Recurring entries use the first available "
        f"{display.recurring_price_label} price in each cadence window."
    )


def normalize_legacy_data_caveat(value: object, *, language: str = "en") -> str:
    text = " ".join(str(value or "").strip().split())
    if not text:
        return ""

    normalized = text.lower().rstrip(".")
    timeframe = _legacy_bars_only_timeframe(normalized)
    if timeframe is not None:
        if _parse_timeframe(timeframe) is not None:
            return format_timeframe_data_caveat(timeframe, language=language)
    if normalized == "recurring entries use the first available bar in each cadence window":
        return format_recurring_entry_caveat("1D", language=language)
    return text


def describe_timeframe(timeframe: object, *, language: str = "en") -> TimeframeDisplay:
    resolved_language = _resolve_language(language)
    raw = str(timeframe or "").strip()
    parsed = _parse_timeframe(raw)
    if parsed is None:
        return _unknown_timeframe(raw, language=resolved_language)
    amount, unit = parsed
    if resolved_language == "es-419":
        data_label = _spanish_data_label(amount=amount, unit=unit, raw=raw)
        recurring_price_label = _spanish_recurring_price_label(amount=amount, unit=unit)
    else:
        data_label = _english_data_label(amount=amount, unit=unit, raw=raw)
        recurring_price_label = _english_recurring_price_label(
            amount=amount,
            unit=unit,
        )
    return TimeframeDisplay(
        raw=raw,
        amount=amount,
        unit=unit,
        language=resolved_language,
        data_label=data_label,
        recurring_price_label=recurring_price_label,
    )


def _parse_timeframe(value: str) -> tuple[int, TimeframeUnit] | None:
    normalized = value.strip().lower().replace("_", "").replace(" ", "")
    if not normalized:
        return None
    if normalized in _TIMEFRAME_ALIASES:
        return _TIMEFRAME_ALIASES[normalized]
    amount_text, unit_text = _split_timeframe_amount_and_unit(normalized)
    if not amount_text or not unit_text:
        return None
    unit = _UNIT_ALIASES.get(unit_text)
    if unit is None:
        return None
    amount = int(amount_text)
    if amount < 1:
        return None
    return amount, unit


def _split_timeframe_amount_and_unit(value: str) -> tuple[str | None, str | None]:
    split_at = 0
    while split_at < len(value) and value[split_at].isdigit():
        split_at += 1
    if split_at == 0 or split_at == len(value):
        return None, None
    return value[:split_at], value[split_at:]


def _legacy_bars_only_timeframe(normalized: str) -> str | None:
    tokens = normalized.replace("_", " ").replace("-", " ").split()
    if len(tokens) == 3 and tokens[1] == "bars" and tokens[2] == "only":
        return tokens[0]
    return None


def _unknown_timeframe(raw: str, *, language: Language) -> TimeframeDisplay:
    fallback = raw or ("predeterminados" if language == "es-419" else "default")
    if language == "es-419":
        return TimeframeDisplay(
            raw=raw,
            amount=None,
            unit=None,
            language=language,
            data_label=f"Datos {fallback}",
            recurring_price_label=fallback.lower(),
        )
    return TimeframeDisplay(
        raw=raw,
        amount=None,
        unit=None,
        language=language,
        data_label=f"{fallback} data".capitalize() if not raw else f"{raw} data",
        recurring_price_label=fallback.lower(),
    )


def _english_data_label(*, amount: int, unit: TimeframeUnit, raw: str) -> str:
    if amount == 1 and unit == "day":
        return "Daily data"
    if amount == 1 and unit == "hour":
        return "Hourly data"
    if amount == 1 and unit == "week":
        return "Weekly data"
    if amount == 1 and unit == "minute":
        return "1-minute data"
    return f"{amount}-{unit} data"


def _english_recurring_price_label(*, amount: int, unit: TimeframeUnit) -> str:
    if amount == 1 and unit == "day":
        return "daily"
    if amount == 1 and unit == "hour":
        return "hourly"
    if amount == 1 and unit == "week":
        return "weekly"
    return f"{amount}-{unit}"


def _spanish_data_label(*, amount: int, unit: TimeframeUnit, raw: str) -> str:
    if amount == 1 and unit == "day":
        return "Datos diarios"
    if amount == 1 and unit == "hour":
        return "Datos por hora"
    if amount == 1 and unit == "week":
        return "Datos semanales"
    return f"Datos de {amount} {_spanish_unit(unit, amount=amount)}"


def _spanish_recurring_price_label(*, amount: int, unit: TimeframeUnit) -> str:
    if amount == 1 and unit == "day":
        return "diario"
    if amount == 1 and unit == "hour":
        return "por hora"
    if amount == 1 and unit == "week":
        return "semanal"
    return f"de {amount} {_spanish_unit(unit, amount=amount)}"


def _spanish_unit(unit: TimeframeUnit, *, amount: int) -> str:
    singular = {
        "minute": "minuto",
        "hour": "hora",
        "day": "dia",
        "week": "semana",
    }[unit]
    if amount == 1:
        return singular
    return f"{singular}s"


def _resolve_language(language: str) -> Language:
    return "es-419" if (language or "en").lower().startswith("es") else "en"


def _locale_identifier(language: str) -> str:
    return "es_419" if _resolve_language(language) == "es-419" else "en_US"


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _english_short_month_day(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}"


def _spanish_short_month_day(value: date) -> str:
    return f"{value.day} {value.strftime('%b').lower()}"


def _lower_initial(value: str) -> str:
    if not value:
        return value
    return value[:1].lower() + value[1:]
