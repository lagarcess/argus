"""Cross-cutting leaf helpers shared across interpret-stage modules (import sink).

Behavior-preserving relocation from stages/interpret.py (issue #131)."""

from __future__ import annotations

from typing import Any

from argus.agent_runtime.capabilities.answers import EXECUTABLE_STRATEGY_FAMILIES
from argus.agent_runtime.interpreter.shared import KNOWN_TURN_ACTS, is_explicit_fresh_task
from argus.agent_runtime.rule_specs import (
    indicator_parameters_from_strategy as canonical_indicator_parameters_from_strategy,
)
from argus.agent_runtime.rule_specs import (
    strategy_rule,
)
from argus.agent_runtime.state.models import StrategySummary
from argus.agent_runtime.strategy_requirements import (
    valid_rule_spec_from_strategy as _valid_rule_spec_from_strategy,
)
from argus.domain.indicators import executable_indicator_spec


def _supported_experiment_fact_packet() -> str:
    families = "; ".join(EXECUTABLE_STRATEGY_FAMILIES)
    return (
        f"{families}. Macro, news, corporate-action, and movers context may frame "
        "a question or explain backdrop, but cannot alter simulation truth or become "
        "the executable rule. Suggested next experiments must stay inside these "
        "families instead of inventing unregistered triggers or holding-period rules."
    )


def _field_base(field_name: str) -> str:
    return field_name.split("[", 1)[0]


def _selected_response_intent(
    selected_thread_metadata: dict[str, Any],
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    root_intent = selected_thread_metadata.get("response_intent")
    if isinstance(root_intent, dict):
        candidates.append(root_intent)
    pending_strategy = selected_thread_metadata.get("pending_strategy")
    if isinstance(pending_strategy, dict):
        nested_intent = pending_strategy.get("response_intent")
        if isinstance(nested_intent, dict):
            candidates.append(nested_intent)
    if not candidates or any(candidate != candidates[0] for candidate in candidates[1:]):
        return None
    return dict(candidates[0])


def _selected_requested_field(
    selected_thread_metadata: dict[str, Any],
) -> str:
    candidates: list[Any] = [selected_thread_metadata.get("requested_field")]
    pending_strategy = selected_thread_metadata.get("pending_strategy")
    if isinstance(pending_strategy, dict):
        candidates.append(pending_strategy.get("requested_field"))
    response_intent = _selected_response_intent(selected_thread_metadata)
    if response_intent is not None:
        requested_fields = response_intent.get("requested_fields")
        if isinstance(requested_fields, list) and len(requested_fields) == 1:
            candidates.append(requested_fields[0])
    normalized = {
        _field_base(str(candidate or "")).strip()
        for candidate in candidates
        if str(candidate or "").strip()
    }
    return next(iter(normalized)) if len(normalized) == 1 else ""


# Provenance sources meaning the user set the money field in THIS turn;
# "prior" (carried context) is deliberately excluded.
_EXPLICIT_TURN_MONEY_SOURCES = frozenset(
    {
        "user",
        "explicit_user",
        "starting_capital",
        "starting_principal",
        "recurring_contribution",
        "contribution_amount",
    }
)


# The runtime asked and is waiting: a reply continues the setup that is
# pending, whatever act the interpreter labeled it. Only an explicit
# fresh-task read (new_idea with new_task) starts over.
_PENDING_SETUP_OUTCOMES = frozenset({"await_user_reply", "await_approval"})
_PENDING_SETUP_TURN_ACTS = KNOWN_TURN_ACTS


# The interpreter's own receipt for filling an empty asset universe from a
# benchmark mention; the one signal that an incoming asset is that repair's
# artifact rather than something the user named.
MISPLACED_BENCHMARK_REPAIR_REASON = "misplaced_benchmark_asset_recovered"


def _turn_continues_pending_setup(
    *,
    prior: StrategySummary | None,
    strategy: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str | None,
    current_user_message: str | None = None,
    reason_codes: list[str] | None = None,
) -> bool:
    if prior is None:
        return False
    if selected_thread_metadata.get("last_stage_outcome") not in _PENDING_SETUP_OUTCOMES:
        return False
    if (
        semantic_turn_act not in _PENDING_SETUP_TURN_ACTS
        and semantic_turn_act is not None
    ):
        return False
    if is_explicit_fresh_task(semantic_turn_act, task_relation):
        # The interpreter's fresh-task read wins, whatever the draft holds:
        # a new task inherits nothing, and what it lacks is asked for.
        return False
    return True


def _pending_setup_continuation_reason_codes(
    *,
    interpretation: Any,
    prior: StrategySummary | None,
    selected_thread_metadata: dict[str, Any],
    current_user_message: str | None = None,
) -> list[str]:
    """Name the override when the runtime kept a setup the model called new."""
    semantic_turn_act = interpretation.semantic_turn_act
    task_relation = interpretation.task_relation
    if semantic_turn_act != "new_idea" and task_relation != "new_task":
        return []
    if not _turn_continues_pending_setup(
        prior=prior,
        strategy=interpretation.candidate_strategy_draft,
        selected_thread_metadata=selected_thread_metadata,
        semantic_turn_act=semantic_turn_act,
        task_relation=task_relation,
        current_user_message=current_user_message,
        reason_codes=list(interpretation.reason_codes),
    ):
        return []
    return ["pending_setup_continuation_merged"]


def _current_turn_has_strong_asset_override(
    *,
    strategy: StrategySummary,
    current_user_message: str | None,
) -> bool:
    for symbol in strategy.asset_universe:
        target = _compact_asset_evidence_token(symbol)
        if not target:
            continue
        if _message_has_cashtag_for_asset(current_user_message, target=target):
            return True
        if _message_has_uppercase_asset_token(current_user_message, target=target):
            return True
        if _strategy_has_strong_asset_evidence(strategy=strategy, target=target):
            return True
    return False


def _strategy_has_strong_asset_evidence(
    *,
    strategy: StrategySummary,
    target: str,
) -> bool:
    evidence_spans = strategy.extra_parameters.get("evidence_spans")
    if isinstance(evidence_spans, dict):
        for field_name, evidence in evidence_spans.items():
            if _field_base(str(field_name)) != "asset_universe":
                continue
            evidence_text = str(evidence or "")
            if _message_has_cashtag_for_asset(evidence_text, target=target):
                return True
            if _message_has_uppercase_asset_token(evidence_text, target=target):
                return True
    for item in strategy.resolution_provenance:
        if _field_base(_provenance_field_name(item)) != "asset_universe":
            continue
        source = getattr(item, "source", None)
        raw_text = getattr(item, "raw_text", "")
        canonical_symbol = getattr(item, "canonical_symbol", "")
        if str(source or "") == "user_mention" and target in {
            _compact_asset_evidence_token(raw_text),
            _compact_asset_evidence_token(canonical_symbol),
        }:
            return True
    return False


def _message_has_cashtag_for_asset(message: str | None, *, target: str) -> bool:
    for token in str(message or "").split():
        cleaned = "".join(
            character
            for character in token.strip()
            if character.isalnum() or character == "$"
        )
        if (
            cleaned.startswith("$")
            and _compact_asset_evidence_token(cleaned[1:]) == target
        ):
            return True
    return False


def _message_has_uppercase_asset_token(message: str | None, *, target: str) -> bool:
    for token in str(message or "").split():
        cleaned = "".join(
            character
            for character in token.strip()
            if character.isalnum() or character in {"/", "-"}
        )
        if not cleaned or cleaned != cleaned.upper():
            continue
        if not any(character.isalpha() and character.isupper() for character in cleaned):
            continue
        if _compact_asset_evidence_token(cleaned) == target:
            return True
    return False


def _compact_asset_evidence_token(value: Any) -> str:
    return "".join(
        character.casefold() for character in str(value or "") if character.isalnum()
    )


def _provenance_field_name(item: Any) -> str:
    field = getattr(item, "field", None)
    if field is None and isinstance(item, dict):
        field = item.get("field")
    return field if isinstance(field, str) else ""


def _strategy_has_explicit_asset_evidence(
    strategy: StrategySummary,
    *,
    symbol: str,
    current_user_message: str | None,
) -> bool:
    target = _compact_asset_evidence_token(symbol)
    if not target:
        return False
    if _message_has_cashtag_for_asset(current_user_message, target=target):
        return True

    field_provenance = strategy.extra_parameters.get("field_provenance")
    if isinstance(field_provenance, dict):
        for field_name, source in field_provenance.items():
            if _field_base(str(field_name)) != "asset_universe":
                continue
            if str(source or "").strip() in {
                "asset_field",
                "asset_mention",
                "cashtag",
                "composer_mention",
                "explicit_user",
                "user",
                "user_mention",
            }:
                return True

    evidence_spans = strategy.extra_parameters.get("evidence_spans")
    if isinstance(evidence_spans, dict):
        for field_name, evidence in evidence_spans.items():
            if _field_base(str(field_name)) != "asset_universe":
                continue
            evidence_text = str(evidence or "")
            if _message_has_cashtag_for_asset(evidence_text, target=target):
                return True

    for item in strategy.resolution_provenance:
        if _field_base(_provenance_field_name(item)) != "asset_universe":
            continue
        source = getattr(item, "source", None)
        raw_text = getattr(item, "raw_text", "")
        canonical_symbol = getattr(item, "canonical_symbol", "")
        if str(source or "") == "user_mention" and target in {
            _compact_asset_evidence_token(raw_text),
            _compact_asset_evidence_token(canonical_symbol),
        }:
            return True
    return False


def _incoming_asset_is_misplaced_benchmark(
    *,
    prior: StrategySummary,
    strategy: StrategySummary,
    reason_codes: list[str] | None,
) -> bool:
    """The asset universe holds only what the benchmark repair put there."""
    if MISPLACED_BENCHMARK_REPAIR_REASON not in set(reason_codes or []):
        return False
    if not strategy.asset_universe:
        return False
    benchmarks = {
        _compact_asset_evidence_token(strategy.comparison_baseline),
        _compact_asset_evidence_token(prior.comparison_baseline),
    } - {""}
    return all(
        _compact_asset_evidence_token(symbol) in benchmarks
        for symbol in strategy.asset_universe
    )


def _strategy_supplies_explicit_turn_money(strategy: StrategySummary) -> bool:
    extra_parameters = strategy.extra_parameters or {}
    field_provenance = extra_parameters.get("field_provenance")
    if not isinstance(field_provenance, dict):
        return False
    has_money_value = strategy.capital_amount is not None or any(
        extra_parameters.get(key) is not None
        for key in ("initial_capital", "recurring_contribution")
    )
    if not has_money_value:
        return False
    return any(
        str(field_provenance.get(key) or "").strip() in _EXPLICIT_TURN_MONEY_SOURCES
        for key in ("capital_amount", "initial_capital", "recurring_contribution")
    )


def _should_preserve_prior_asset_context(
    *,
    prior: StrategySummary,
    selected_thread_metadata: dict[str, Any],
    semantic_turn_act: str | None,
    task_relation: str,
) -> bool:
    if not prior.asset_universe:
        return False
    if semantic_turn_act != "answer_pending_need":
        return False
    if task_relation not in {"continue", "refine"}:
        return False
    requested_field = _field_base(
        str(selected_thread_metadata.get("requested_field") or "")
    )
    if requested_field == "asset_universe":
        return False
    return selected_thread_metadata.get("last_stage_outcome") == "await_user_reply"


def _strategy_supplies_executable_rule_edit(strategy: StrategySummary) -> bool:
    indicator_parameters = canonical_indicator_parameters_from_strategy(strategy)
    indicator = str(indicator_parameters.get("indicator") or "").strip()
    return bool(
        strategy_rule(strategy, "entry")
        or strategy_rule(strategy, "exit")
        or _valid_rule_spec_from_strategy(strategy)
        or (indicator and executable_indicator_spec(indicator) is not None)
    )
