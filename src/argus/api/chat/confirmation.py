from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from argus.agent_runtime.confirmation_artifacts import (
    canonical_payload_hash,
    confirmation_id_from_payload,
    stable_payload_hash,
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.confirmation_facts import (
    confirmation_dca_starting_capital as _confirmation_dca_starting_capital,
)
from argus.agent_runtime.confirmation_facts import (
    confirmation_display_capital as _confirmation_display_capital,
)
from argus.agent_runtime.confirmation_facts import (
    confirmation_display_facts,
)
from argus.agent_runtime.confirmation_facts import (
    strategy_type_uses_cadence as _strategy_type_uses_cadence,
)
from argus.agent_runtime.presentation_i18n import confirmation_rule_display_value
from argus.agent_runtime.strategy_contract import (
    display_strategy_slug,
    display_strategy_type,
    executable_strategy_type,
    resolve_date_range,
)
from argus.api.chat.confirmation_lifecycle import (
    DeadConfirmationCardError,
    _sync_runtime_checkpoint_with_card,
    apply_pending_card_update,
    consume_confirmation_for_admitted_run,
    consume_pending_card_for_run,
    restore_pending_card_after_run,
    restore_pending_card_for_failed_job,
)
from argus.api.chat.confirmation_research_peers import (
    attach_research_peer_rows,
    research_peer_add_rows_for_confirmation,
    research_peers_from_transcript,
)
from argus.domain.backtesting.config import (
    _execution_realism_feature_enabled,
)
from argus.domain.engine_launch.display import (
    format_date_range_label,
)
from argus.domain.market_data.new_york_clock import new_york_today

# This module is the confirmation card's builder and the import path every
# caller and test already holds. The lifecycle and research-peer names below
# are defined in their own modules and re-exported here, so a name resolves to
# one definition wherever it is imported or patched from.
__all__ = [
    "DeadConfirmationCardError",
    "_sync_runtime_checkpoint_with_card",
    "apply_pending_card_update",
    "attach_research_peer_rows",
    "consume_confirmation_for_admitted_run",
    "consume_pending_card_for_run",
    "public_confirmation_projection",
    "research_peer_add_rows_for_confirmation",
    "research_peers_from_transcript",
    "restore_pending_card_after_run",
    "restore_pending_card_for_failed_job",
    "runtime_confirmation_card",
]


def public_confirmation_projection(value: Any) -> Any:
    """Remove private durable confirmation identity from public transport data."""
    if isinstance(value, dict):
        return {
            key: public_confirmation_projection(item)
            for key, item in value.items()
            if key != "canonical_launch_payload_hash"
        }
    if isinstance(value, list):
        return [public_confirmation_projection(item) for item in value]
    return value


def runtime_confirmation_card(
    runtime_result: dict[str, Any],
    *,
    confirmation_id: str | None = None,
    conversation_id: str | None = None,
    format_confirmation_period_func: Any | None = None,
    language: str = "en",
) -> dict[str, Any] | None:
    if runtime_result.get("stage_outcome") != "await_approval":
        return None
    payload = runtime_result.get("confirmation_payload")
    if not isinstance(payload, dict):
        return None
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    optional_parameters = payload.get("optional_parameters")
    if not isinstance(optional_parameters, dict):
        optional_parameters = {}

    symbols = [
        str(symbol)
        for symbol in strategy.get("asset_universe", [])
        if str(symbol).strip()
    ]
    assets = ", ".join(symbols) if symbols else "Selected asset"
    strategy_type = display_strategy_slug(strategy)
    strategy_label = display_strategy_type(strategy)
    if format_confirmation_period_func is not None:
        date_range = format_confirmation_period_func(strategy.get("date_range"))
    else:
        date_range = _format_confirmation_period(
            strategy.get("date_range"),
            language=language,
        )
    canonical_date_range = _confirmation_date_range_payload(
        strategy.get("date_range"),
        display=date_range,
    )
    title = _confirmation_title(assets=assets, strategy_type=strategy_type)
    launch_payload = payload.get("launch_payload")
    if not isinstance(launch_payload, dict):
        launch_payload = {}
    canonical_strategy_type = executable_strategy_type(strategy)

    rows = [
        _confirmation_row("strategy", "Strategy", strategy_label),
        _confirmation_row("assets", "Assets", assets),
        _confirmation_row("period", "Period", date_range),
    ]
    if strategy.get("entry_logic"):
        rows.append(
            _confirmation_row(
                "buy_rule",
                "Buy rule",
                _format_confirmation_rule_value(
                    strategy,
                    side="entry",
                    value=strategy["entry_logic"],
                    language=language,
                ),
            )
        )
    if strategy.get("exit_logic"):
        rows.append(
            _confirmation_row(
                "exit_rule",
                "Exit rule",
                _format_confirmation_rule_value(
                    strategy,
                    side="exit",
                    value=strategy["exit_logic"],
                    language=language,
                ),
            )
        )
    display_capital = _confirmation_display_capital(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
        strategy_type=canonical_strategy_type,
    )
    if _strategy_type_uses_cadence(canonical_strategy_type):
        # Two rows, exactly the two parameters a recurring plan has. The
        # contribution is one phrase because nobody has a period on its own.
        rows.append(
            _confirmation_row(
                "starting_capital",
                "Starting capital",
                f"${_confirmation_dca_starting_capital(optional_parameters):,.0f}",
            )
        )
        if display_capital is not None:
            rows.append(
                _confirmation_row(
                    "contribution",
                    "Contribution",
                    _contribution_row_value(display_capital, strategy=strategy),
                )
            )
    elif display_capital is not None:
        rows.append(
            _confirmation_row(
                "starting_capital",
                "Starting capital",
                f"${display_capital:,.0f}",
            )
        )

    display_facts = confirmation_display_facts(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
    )
    summary_period = _confirmation_period_without_parentheses(date_range)
    summary = _confirmation_summary(
        assets=assets,
        strategy=strategy,
        strategy_label=strategy_label,
        period=summary_period,
    )
    active_confirmation_id = confirmation_id_from_payload(
        payload,
        fallback=confirmation_id or f"confirmation-{uuid4()}",
    )
    execution_validation = validate_confirmation_execution_payload(payload)
    retest_period = _retest_period_from_confirmation_payload(payload)
    has_retest_period = "retest_period" in payload
    is_ready_to_run = execution_validation.executable and (
        not has_retest_period or retest_period is not None
    )
    owner_conversation_id = conversation_id.strip() if conversation_id else None
    action_payload = {
        "confirmation_id": active_confirmation_id,
        "artifact_id": active_confirmation_id,
        "launch_payload_hash": stable_payload_hash(execution_validation.launch_payload),
    }
    if owner_conversation_id:
        action_payload["conversation_id"] = owner_conversation_id
    # §3.1 end state: Run backtest, Change assumptions, Cancel. The scoped
    # change_dates/change_asset entry points are retired from emission only,
    # gated on the §3.2 compound-edit contract: the general entry point now
    # applies every stated change or discloses what it could not, and capital
    # and dates additionally have the direct drawer. The action types stay in
    # the schema and the renderer so durable transcripts keep hydrating.
    actions = [
        {
            "id": "adjust-assumptions",
            "type": "adjust_assumptions",
            "label": "Change assumptions",
            "labelKey": "chat.confirmation.actions.adjust_assumptions",
            "presentation": "confirmation",
            "payload": action_payload,
        },
        {
            "id": "cancel-confirmation",
            "type": "cancel_confirmation",
            "label": "Cancel",
            "labelKey": "chat.confirmation.actions.cancel",
            "presentation": "confirmation",
            "payload": action_payload,
        },
    ]
    if is_ready_to_run:
        actions.insert(
            0,
            {
                "id": "run-backtest",
                "type": "run_backtest",
                "label": "Run backtest",
                "labelKey": "chat.confirmation.actions.run_backtest",
                "presentation": "confirmation",
                "payload": action_payload,
            },
        )
    card: dict[str, Any] = {
        "kind": "backtest",
        "confirmation_id": active_confirmation_id,
        "confirmation_state": "active",
        "launch_payload_hash": stable_payload_hash(execution_validation.launch_payload),
        "canonical_launch_payload_hash": canonical_payload_hash(
            execution_validation.launch_payload
        ),
        "title": title,
        "status": "ready_to_run" if is_ready_to_run else "needs_change",
        "statusLabel": _confirmation_status_label(is_ready_to_run=is_ready_to_run),
        "strategy_type": canonical_strategy_type,
        "summary": summary,
        "rows": rows,
        "assumptions": [],
        "actions": actions,
    }
    if display_facts:
        card["display_facts"] = display_facts
    capabilities: dict[str, Any] = {}
    if _execution_realism_feature_enabled():
        # Backend capability truth: the engine can apply fee/slippage
        # assumptions, so the confirmation surface may offer editing them.
        capabilities["execution_costs_editable"] = True
    # Direct no-turn edits the typed endpoint accepts for this card. Capital
    # follows the launch sizing mode; dates are always directly editable;
    # costs join whenever the engine can model them, so all three edit
    # affordances share one in-place behaviour. While the in-place surface
    # is dark the card advertises none, and the frontend, which renders
    # backend truth, shows no pills.
    from argus.domain.edit_contract_config import in_place_card_edits_enabled

    if in_place_card_edits_enabled():
        direct_edits = ["dates"]
        if str(launch_payload.get("sizing_mode") or "capital_amount") != "position_size":
            direct_edits.insert(0, "capital")
        if capabilities.get("execution_costs_editable"):
            direct_edits.append("costs")
        capabilities["direct_edits"] = direct_edits
        capabilities["edit_constraints"] = _edit_constraints(
            strategy,
            launch_payload=launch_payload,
        )
    card["capabilities"] = capabilities
    asset_class = _confirmation_asset_class(strategy)
    if asset_class is not None:
        card["asset_class"] = asset_class
    if canonical_date_range is not None:
        card["date_range"] = canonical_date_range
    if retest_period is not None:
        card["retest_period"] = retest_period
    period_adjustment = _period_adjustment_from_launch_payload(launch_payload)
    if period_adjustment is not None:
        card["period_adjustment"] = period_adjustment
    benchmark_adjustment = _benchmark_adjustment_from_strategy(strategy)
    if benchmark_adjustment is not None:
        card["benchmark_adjustment"] = benchmark_adjustment
    assets_adjustment = payload.get("assets_adjustment")
    if isinstance(assets_adjustment, dict):
        # Typed change data, never a banner: it drives the new-chip motion
        # and the inline period disclosure; the deliberate add itself is not
        # narrated back to the user.
        card["assets_adjustment"] = dict(assets_adjustment)
    edit_disclosure = payload.get("edit_disclosure")
    if isinstance(edit_disclosure, dict):
        # §3.2: the part of an edit that could not be applied is disclosed on
        # the card the edit produced. Card turns drop assistant prose, so the
        # typed record is the only channel that reaches the user.
        card["edit_disclosure"] = dict(edit_disclosure)
    return card


def _edit_constraints(
    strategy: dict[str, Any],
    *,
    launch_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The accepted-value envelope this card's edits must satisfy.

    Backend canonical truth: the values are the engine's own bounds, imported
    rather than restated, so the client can render and pre-check them without
    ever owning them. The date floor follows the card's asset class because
    provider history does.
    """
    from argus.domain.backtesting.config import (
        MAX_FEE_RATE,
        MAX_SLIPPAGE_RATE,
        MAX_STARTING_CAPITAL,
        MIN_STARTING_CAPITAL,
    )
    from argus.domain.market_data.capabilities import ALPACA_EQUITY_HISTORY_START

    date_window: dict[str, Any] = {"max_end": new_york_today().isoformat()}
    if str(strategy.get("asset_class") or "") == "equity":
        date_window["min_start"] = ALPACA_EQUITY_HISTORY_START.isoformat()
    capital: dict[str, Any] = {"max": MAX_STARTING_CAPITAL}
    constraints: dict[str, Any] = {
        "capital": capital,
        "fees": {"min": 0.0, "max": MAX_FEE_RATE},
        "slippage": {"min": 0.0, "max": MAX_SLIPPAGE_RATE},
        "date_window": date_window,
    }
    if str(strategy.get("strategy_type") or "") != "dca_accumulation":
        capital["min"] = MIN_STARTING_CAPITAL
        return constraints

    # A recurring plan edits two money roles and a period. The seed has no
    # floor because $0 is its default, and the offered periods are only the
    # ones that fit the card's own window, so the picker can never present a
    # pair the engine would refuse.
    # The contribution advertises no floor for the same reason the seed's is
    # zero: the plan's rule is "some money", not "at least this much", and
    # restating it as a number here would be a second, stricter rule.
    constraints["starting_capital"] = {"min": 0.0, "max": MAX_STARTING_CAPITAL}
    constraints["contribution"] = {
        "max": MAX_STARTING_CAPITAL,
        "periods": _contribution_periods_for_strategy(
            strategy,
            launch_payload=launch_payload or {},
        ),
    }
    return constraints


def _contribution_periods_for_strategy(
    strategy: dict[str, Any],
    *,
    launch_payload: dict[str, Any],
) -> list[str]:
    """Only periods that fit at least once inside this card's window.

    Both windows come from the coverage payload, the same place the request
    model reads them. A materialized strategy has already had its date range
    replaced by the served window, so deriving the request from it would
    advertise fewer periods than the engine actually accepts.
    """
    from argus.domain.dca_capital import (
        contribution_period_window,
        contribution_periods_for_window,
    )

    coverage = launch_payload.get("coverage_preflight")
    coverage = coverage if isinstance(coverage, dict) else {}
    requested = _coverage_window(coverage.get("requested_date_range"))
    effective = _coverage_window(coverage.get("effective_date_range"))
    if effective is None:
        try:
            resolved = resolve_date_range(
                strategy.get("date_range"), today=_confirmation_today()
            )
        except (TypeError, ValueError):
            return []
        requested, effective = None, (resolved.start, resolved.end)
    start, end = contribution_period_window(
        requested=requested,
        effective=effective,
        adjustment_reason=coverage.get("adjustment_reason"),
    )
    return list(contribution_periods_for_window(start=start, end=end))


def _benchmark_adjustment_from_strategy(
    strategy: dict[str, Any],
) -> dict[str, Any] | None:
    """The user's named comparison target that could not be executed rides
    the strategy's resolution provenance; the card owns disclosing the swap."""
    effective = str(strategy.get("comparison_baseline") or "").strip()
    if not effective:
        return None
    for item in strategy.get("resolution_provenance") or []:
        if not isinstance(item, dict):
            continue
        if (
            item.get("field") == "comparison_baseline"
            and item.get("resolution_status")
            in {"unsupported", "ambiguous", "unavailable_for_requested_run"}
            and str(item.get("raw_text") or "").strip()
        ):
            return {
                "code": "comparison_target_unsupported",
                "requested_target": str(item["raw_text"]).strip(),
                "effective_benchmark": effective,
            }
    return None


def _period_adjustment_from_launch_payload(
    launch_payload: dict[str, Any],
) -> dict[str, Any] | None:
    coverage = launch_payload.get("coverage_preflight")
    if (
        not isinstance(coverage, dict)
        or coverage.get("outcome") != "adjusted_coverage"
        or coverage.get("adjustment_reason") != "provider_coverage_adjustment"
    ):
        return None
    requested = _date_range_payload(coverage.get("requested_date_range"))
    effective = _date_range_payload(coverage.get("effective_date_range"))
    if requested is None or effective is None:
        return None
    adjustment: dict[str, Any] = {
        "code": "effective_window_adjusted",
        "requested_date_range": dict(requested),
        "effective_date_range": dict(effective),
    }
    limited_by = _limited_by_payload(coverage.get("limited_by"))
    if limited_by is not None:
        adjustment["limited_by"] = limited_by
    return adjustment


def _limited_by_payload(value: Any) -> dict[str, str] | None:
    if not (
        isinstance(value, dict)
        and isinstance(value.get("symbol"), str)
        and value["symbol"].strip()
        and isinstance(value.get("first_available"), str)
    ):
        return None
    return {
        "symbol": value["symbol"].strip(),
        "first_available": value["first_available"],
    }


def _coverage_window(value: Any) -> tuple[date, date] | None:
    payload = _date_range_payload(value)
    if payload is None:
        return None
    try:
        return date.fromisoformat(payload["start"]), date.fromisoformat(payload["end"])
    except ValueError:
        return None


def _date_range_payload(value: Any) -> dict[str, str] | None:
    if not (
        isinstance(value, dict)
        and isinstance(value.get("start"), str)
        and isinstance(value.get("end"), str)
    ):
        return None
    return {"start": value["start"], "end": value["end"]}


def _retest_period_from_confirmation_payload(
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    value = payload.get("retest_period")
    if not isinstance(value, dict):
        return None
    original = _validated_retest_date_range(value.get("original_date_range"))
    requested = _validated_retest_date_range(value.get("requested_date_range"))
    effective = _validated_retest_date_range(value.get("effective_date_range"))
    if original is None or requested is None or effective is None:
        return None

    duration_days = value.get("duration_days")
    duration = value.get("duration")
    if (
        not isinstance(duration_days, int)
        or isinstance(duration_days, bool)
        or duration_days < 0
        or not isinstance(duration, dict)
    ):
        return None
    unit = duration.get("unit")
    count = duration.get("count")
    approximate = duration.get("approximate")
    if (
        unit not in {"year", "month", "day"}
        or not isinstance(count, int | float)
        or isinstance(count, bool)
        or count < 0
        or not isinstance(approximate, bool)
    ):
        return None
    effective_days = (
        date.fromisoformat(effective["end"]) - date.fromisoformat(effective["start"])
    ).days
    if duration_days != effective_days:
        return None
    return {
        "original_date_range": original,
        "requested_date_range": requested,
        "effective_date_range": effective,
        "duration_days": duration_days,
        "duration": {
            "unit": unit,
            "count": count,
            "approximate": approximate,
        },
    }


def _validated_retest_date_range(value: Any) -> dict[str, str] | None:
    date_range = _date_range_payload(value)
    if date_range is None:
        return None
    try:
        start = date.fromisoformat(date_range["start"])
        end = date.fromisoformat(date_range["end"])
    except ValueError:
        return None
    if start > end:
        return None
    return {"start": start.isoformat(), "end": end.isoformat()}


def _confirmation_asset_class(strategy: dict[str, Any]) -> str | None:
    asset_class = strategy.get("asset_class")
    if asset_class in {"equity", "crypto", "currency_pair"}:
        return str(asset_class)
    return None


def _confirmation_row(key: str, label: str, value: str) -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "labelKey": f"chat.confirmation.rows.{key}",
        "value": value,
    }


def _supported_contribution_period(value: Any) -> str | None:
    from argus.domain.dca_capital import supported_contribution_period

    return supported_contribution_period(value)


def _contribution_row_value(amount: float, *, strategy: dict[str, Any]) -> str:
    """The amount and its period as one phrase, never two labelled parameters."""
    from argus.domain.backtesting.cards import format_contribution_phrase

    period = _supported_contribution_period(strategy.get("cadence"))
    if period is None:
        return f"${amount:,.0f}"
    return format_contribution_phrase(amount=amount, period=period, is_es=False)


def _confirmation_date_range_payload(
    value: Any,
    *,
    display: str,
) -> dict[str, str] | None:
    try:
        resolved = resolve_date_range(value, today=_confirmation_today())
    except (TypeError, ValueError):
        return None
    return {
        "start": resolved.start.isoformat(),
        "end": resolved.end.isoformat(),
        "display": display,
    }


def _confirmation_summary(
    *,
    assets: str,
    strategy: dict[str, Any],
    strategy_label: str,
    period: str,
) -> str:
    strategy_type = executable_strategy_type(strategy)
    if strategy_type == "buy_and_hold":
        return f"Ready to test buy-and-hold for {assets} over {period}."
    if _strategy_type_uses_cadence(strategy_type):
        return f"Ready to test recurring buys for {assets} over {period}."
    return (
        f"Ready to test {assets} with "
        f"{_summary_strategy_phrase(strategy_label)} over {period}."
    )


def _summary_strategy_phrase(strategy_label: str) -> str:
    phrases = {
        "RSI Threshold": "an RSI threshold",
        "Dip Buying": "a dip-buying rule",
        "Indicator Threshold": "an indicator threshold",
        "Signal Strategy": "a signal strategy",
        "Moving Average Crossover": "a moving-average crossover",
    }
    return phrases.get(strategy_label, strategy_label.strip().lower())


def _format_confirmation_value(value: Any) -> str:
    if isinstance(value, dict):
        start = value.get("start") or value.get("from")
        end = value.get("end") or value.get("to")
        if start and end:
            return f"{start} to {end}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None or value == "":
        return "Default period"
    return str(value)


def _format_confirmation_rule_value(
    strategy: dict[str, Any],
    *,
    side: str,
    value: Any,
    language: str,
) -> str:
    return confirmation_rule_display_value(
        strategy,
        side=side,
        fallback_value=value,
        language=language,
    ) or _format_confirmation_value(value)


def _format_confirmation_period(value: Any, *, language: str = "en") -> str:
    resolved = resolve_date_range(value, today=_confirmation_today())
    return format_date_range_label(resolved.start, resolved.end, language=language)


def _confirmation_period_without_parentheses(value: str) -> str:
    if "(" not in value or not value.endswith(")"):
        return value
    label, _, dates = value.partition("(")
    return f"{label.strip()}, {dates[:-1].strip()}"


def _article_for(value: str) -> str:
    return "an" if value[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _confirmation_title(*, assets: str, strategy_type: str) -> str:
    return f"{assets} {strategy_type}".strip()


def _confirmation_status_label(*, is_ready_to_run: bool) -> str:
    return "Ready to run" if is_ready_to_run else "Needs change"


def _confirmation_today() -> date:
    return new_york_today()
