from __future__ import annotations

import re

from pydantic import BaseModel, Field

from argus.agent_runtime.capabilities.contract import CapabilityContract
from argus.agent_runtime.signals.task_relation import detect_symbols, extract_date_range
from argus.agent_runtime.state.models import (
    AmbiguousField,
    ExtractedFieldValue,
    SimplificationOption,
    UnsupportedConstraint,
)
from argus.domain.market_data import resolve_asset


class StrategyExtractionResult(BaseModel):
    strategy_thesis: ExtractedFieldValue
    asset_universe: ExtractedFieldValue
    entry_logic: ExtractedFieldValue
    exit_logic: ExtractedFieldValue
    date_range: ExtractedFieldValue
    ambiguous_fields: list[AmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[UnsupportedConstraint] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


def extract_strategy_fields(
    message: str,
    contract: CapabilityContract,
) -> StrategyExtractionResult:
    normalized_message = normalize_message(message)
    ambiguous_fields = detect_ambiguous_fields(message=message)
    unsupported_constraints = detect_unsupported_constraints(
        message=message,
        contract=contract,
    )
    asset_universe = extract_asset_universe(message=normalized_message)
    entry_logic = extract_entry_logic(message=message)
    exit_logic = extract_exit_logic(
        message=message,
        ambiguous_fields=ambiguous_fields,
    )
    date_range = extract_strategy_date_range(message=normalized_message)

    return StrategyExtractionResult(
        strategy_thesis=extract_strategy_thesis(
            message=message,
            asset_universe=asset_universe,
        ),
        asset_universe=asset_universe,
        entry_logic=entry_logic,
        exit_logic=exit_logic,
        date_range=date_range,
        ambiguous_fields=ambiguous_fields,
        unsupported_constraints=unsupported_constraints,
        reason_codes=collect_reason_codes(
            ambiguous_fields=ambiguous_fields,
            unsupported_constraints=unsupported_constraints,
        ),
    )


def normalize_message(message: str) -> str:
    return re.sub(r"\s+", " ", message.strip().lower())


def extract_strategy_thesis(
    *,
    message: str,
    asset_universe: ExtractedFieldValue,
) -> ExtractedFieldValue:
    if asset_universe.status == "resolved":
        return ExtractedFieldValue(
            raw_value=message.strip(),
            normalized_value=message.strip(),
            status="resolved",
        )
    return ExtractedFieldValue(status="missing")


def extract_asset_universe(*, message: str) -> ExtractedFieldValue:
    symbols = detect_symbols(message)
    if not symbols:
        return ExtractedFieldValue(status="missing")
    return ExtractedFieldValue(
        raw_value=", ".join(symbols),
        normalized_value=symbols[0] if len(symbols) == 1 else symbols,
        status="resolved",
    )


def extract_entry_logic(*, message: str) -> ExtractedFieldValue:
    lowered = normalize_message(message)
    match = re.search(
        r"(?:buy|enter)\s+when\s+(.+?)(?=,\s*(?:sell|exit)\s+when\b|\s+and\s+(?:sell|exit)\s+when\b|$)",
        lowered,
        flags=re.IGNORECASE,
    )
    if match is None:
        return ExtractedFieldValue(status="missing")
    raw_value = match.group(0).strip()
    condition = match.group(1).strip()
    normalized_condition = normalize_logic_condition(condition)
    return ExtractedFieldValue(
        raw_value=raw_value,
        normalized_value=f"enter when {normalized_condition}",
        status="resolved",
    )


def extract_exit_logic(
    *,
    message: str,
    ambiguous_fields: list[AmbiguousField],
) -> ExtractedFieldValue:
    lowered = normalize_message(message)
    if any(field.field_name == "exit_logic" for field in ambiguous_fields):
        raw_value = extract_raw_exit_phrase(lowered)
        return ExtractedFieldValue(
            raw_value=raw_value,
            normalized_value="exit when RSI rises above 70",
            status="ambiguous",
        )

    match = re.search(
        r"(?:sell|exit|close)\s+when\s+(.+?)(?=\s+(?:over the last|last|from \d{4}-\d{2}-\d{2}\b)|[\.,;]|$)",
        lowered,
        flags=re.IGNORECASE,
    )
    if match is None:
        return ExtractedFieldValue(status="missing")
    raw_value = match.group(0).strip()
    condition = match.group(1).strip()
    normalized_condition = normalize_logic_condition(condition)
    return ExtractedFieldValue(
        raw_value=raw_value,
        normalized_value=f"exit when {normalized_condition}",
        status="resolved",
    )


def extract_strategy_date_range(*, message: str) -> ExtractedFieldValue:
    since_match = re.search(r"\bsince\s+(\d{4})\b", message, flags=re.IGNORECASE)
    if since_match is not None:
        raw_value = since_match.group(0)
        return ExtractedFieldValue(
            raw_value=raw_value,
            normalized_value=raw_value,
            status="resolved",
        )

    date_range = extract_date_range(message)
    if date_range is None:
        return ExtractedFieldValue(status="missing")
    return ExtractedFieldValue(
        raw_value=date_range,
        normalized_value=date_range,
        status="resolved",
    )


def detect_ambiguous_fields(*, message: str) -> list[AmbiguousField]:
    lowered = normalize_message(message)
    if re.search(
        r"(?:sell|exit|close)\s+when\s+.*\b(?:not|unless|except)\b",
        lowered,
    ):
        return [
            AmbiguousField(
                field_name="exit_logic",
                raw_value=extract_raw_exit_phrase(lowered),
                candidate_normalized_value="exit when RSI rises above 70",
                reason_code="negation_or_conditional_reversal",
            )
        ]
    return []


def detect_unsupported_constraints(
    *,
    message: str,
    contract: CapabilityContract,
) -> list[UnsupportedConstraint]:
    lowered = normalize_message(message)
    unsupported_constraints: list[UnsupportedConstraint] = []
    if "market open" in lowered:
        unsupported_constraints.append(
            UnsupportedConstraint(
                category="unsupported_time_granularity",
                raw_value="market open",
                explanation="Market-open execution timing is not supported in this runtime slice.",
                simplification_options=contract.get_simplification_options(
                    "unsupported_time_granularity"
                ),
            )
        )
    symbols = detect_symbols(lowered)
    asset_classes = set()
    for symbol in symbols:
        try:
            asset_classes.add(resolve_asset(symbol).asset_class)
        except Exception:
            continue
    if len(asset_classes) > 1:
        unsupported_constraints.append(
            UnsupportedConstraint(
                category="unsupported_asset_mix",
                raw_value=", ".join(symbols),
                explanation=(
                    "I understand that you want to test these assets together, "
                    "but Argus Alpha cannot run equity and crypto in one simulation yet."
                ),
                simplification_options=contract.get_simplification_options(
                    "unsupported_asset_mix"
                ),
            )
        )
    return unsupported_constraints


def collect_reason_codes(
    *,
    ambiguous_fields: list[AmbiguousField],
    unsupported_constraints: list[UnsupportedConstraint],
) -> list[str]:
    reason_codes = [field.reason_code for field in ambiguous_fields]
    reason_codes.extend(
        constraint.category for constraint in unsupported_constraints
    )
    return reason_codes


def extract_raw_exit_phrase(message: str) -> str:
    match = re.search(
        r"(?:sell|exit|close)\s+when\s+(.+?)(?=\s+(?:over the last|last|from \d{4}-\d{2}-\d{2}\b)|[\.,;]|$)",
        message,
        flags=re.IGNORECASE,
    )
    if match is None:
        return "sell when"
    return match.group(0).strip()


def normalize_logic_condition(condition: str) -> str:
    normalized = condition.strip()
    normalized = re.sub(
        r"\brsi\s+is\s+above\s+(\d+)\b",
        r"RSI rises above \1",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\brsi\s+above\s+(\d+)\b",
        r"RSI rises above \1",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"\brsi\s+drops\s+below\s+(\d+)\b",
        r"RSI drops below \1",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized
