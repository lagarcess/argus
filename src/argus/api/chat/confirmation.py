from __future__ import annotations

import threading
from datetime import date
from typing import Any
from uuid import uuid4

from loguru import logger

from argus.agent_runtime.confirmation_artifacts import (
    canonical_payload_hash,
    confirmation_id_from_payload,
    stable_payload_hash,
    validate_confirmation_execution_payload,
)
from argus.agent_runtime.presentation_i18n import confirmation_rule_display_value
from argus.agent_runtime.strategy_contract import (
    display_strategy_slug,
    display_strategy_type,
    executable_strategy_type,
    resolve_date_range,
)
from argus.domain.backtesting.config import (
    _execution_realism_feature_enabled,
    _normalize_execution_realism,
)
from argus.domain.engine_launch.display import (
    format_data_through_label,
    format_date_range_label,
    format_timeframe_data_label,
)


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

    assumptions = _confirmation_assumptions(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
        language=language,
    )
    display_facts = _confirmation_display_facts(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
    )
    # Typed seeds for the direct capital editor; rows carry display strings
    # only, and the frontend must not parse them back into numbers. A recurring
    # plan seeds both of its roles under their own names.
    if _strategy_type_uses_cadence(canonical_strategy_type):
        display_facts["starting_capital"] = _confirmation_dca_starting_capital(
            optional_parameters
        )
        if display_capital is not None:
            display_facts["recurring_contribution"] = display_capital
        contribution_period = _supported_contribution_period(strategy.get("cadence"))
        if contribution_period is not None:
            display_facts["contribution_period"] = contribution_period
    elif display_capital is not None:
        display_facts["capital"] = display_capital
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
        "assumptions": assumptions,
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

    date_window: dict[str, Any] = {"max_end": date.today().isoformat()}
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


class DeadConfirmationCardError(ValueError):
    """The card is no longer a live pending confirmation; nothing was written."""


def _card_message_for_state(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    gateway: Any | None,
) -> Any | None:
    if gateway is not None:
        try:
            return gateway.get_message(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )
        except Exception:  # noqa: BLE001
            return None
    return _persisted_card_message(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )


def _stamped_card_metadata(metadata: dict[str, Any], state: str) -> dict[str, Any]:
    """A copy of the card message metadata carrying the liveness state."""
    import copy as _copy

    stamped = _copy.deepcopy(metadata)
    card = stamped.get("confirmation_card")
    if isinstance(card, dict):
        card["confirmation_state"] = state
    reference = stamped.get("active_confirmation_reference")
    if isinstance(reference, dict):
        reference["artifact_status"] = state
    references = stamped.get("artifact_references")
    if isinstance(references, list):
        for item in references:
            if isinstance(item, dict) and item.get("artifact_type") == "confirmation":
                item["artifact_status"] = state
    return stamped


def _write_card_state(
    *,
    user_id: str,
    conversation_id: str,
    message: Any,
    state: str,
    gateway: Any | None,
) -> None:
    from argus.api.message_store import update_message_artifact

    stamped = _stamped_card_metadata(message.metadata, state)
    if gateway is not None:
        gateway.update_message_artifact(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message.id,
            content=message.content,
            metadata=stamped,
            expected_source_metadata=message.metadata,
            expected_latest_message_id=None,
        )
        return
    update_message_artifact(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message.id,
        content=message.content,
        metadata=stamped,
        expected_source_metadata=message.metadata,
        expected_latest_message_id=None,
    )


def consume_pending_card_for_run(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    expected_launch_payload_hash: str | None = None,
    gateway: Any | None = None,
) -> str:
    """Stamp the card consumed at run admission; the card row is the truth.

    Pressing Run is a commitment: once a run is admitted for a card, the
    card is no longer pending, whatever the job later does. Returns
    ``consumed`` when this call stamped the card, ``already_consumed`` on a
    replay of an admitted run, ``stale_card`` when the card changed between
    the click and admission (its launch payload hash no longer matches the
    admitted run, or an edit keeps winning the row), in which case the run
    must not dispatch, and ``unstamped`` when the card row cannot be read
    at all, in which case the run proceeds without a stamp and the legacy
    newer-message clause covers liveness once its result lands. The write
    is guarded; a lost race re-reads once and re-decides, so a concurrent
    edit and a consumption can never both win the row.
    """
    from argus.agent_runtime.stages.artifact_context import (
        CONSUMED_CONFIRMATION_STATE,
        confirmation_card_is_dead,
    )
    from argus.domain.supabase_conversation_messages import (
        StaleMessageArtifactError,
    )

    for _ in range(2):
        message = _card_message_for_state(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            gateway=gateway,
        )
        if message is None or not isinstance(message.metadata, dict):
            return "unstamped"
        if confirmation_card_is_dead(message.metadata):
            return "already_consumed"
        if expected_launch_payload_hash:
            reference = message.metadata.get("active_confirmation_reference")
            reference_metadata = (
                reference.get("metadata") if isinstance(reference, dict) else None
            )
            current_hash = str(
                (reference_metadata or {}).get("launch_payload_hash") or ""
            ).strip()
            if current_hash and current_hash != expected_launch_payload_hash:
                # The click's basis is gone: an edit rewrote the card after
                # the run was requested, so the run refuses as stale rather
                # than executing values the card no longer shows.
                return "stale_card"
        try:
            _write_card_state(
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
                state=CONSUMED_CONFIRMATION_STATE,
                gateway=gateway,
            )
            return "consumed"
        except StaleMessageArtifactError:
            continue
        except Exception:  # noqa: BLE001
            # The stamp is protective; a store that cannot write it must
            # degrade to the legacy behaviour, never fail the run.
            logger.opt(exception=True).warning(
                "Run consumption stamp could not be written; proceeding "
                "unstamped with legacy liveness",
                conversation_id=conversation_id,
                message_id=message_id,
            )
            return "unstamped"
    return "stale_card"


def restore_pending_card_after_run(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
    gateway: Any | None = None,
) -> bool:
    """Restore a consumed card to active when its run died without a result.

    Only a consumed card is restored; a cancelled or superseded card stays
    dead, so a failed run can never resurrect a card the user closed. The
    checkpoint is not written here: recovery derives liveness from the card
    row, and the next turn's metadata fallback carries the restored card.
    """
    from argus.agent_runtime.stages.artifact_context import (
        ACTIVE_CONFIRMATION_STATE,
        CONSUMED_CONFIRMATION_STATE,
    )
    from argus.domain.supabase_conversation_messages import (
        StaleMessageArtifactError,
    )

    for _ in range(2):
        message = _card_message_for_state(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
            gateway=gateway,
        )
        if message is None or not isinstance(message.metadata, dict):
            return False
        card = message.metadata.get("confirmation_card")
        state = str((card or {}).get("confirmation_state") or "").strip().casefold()
        if state == ACTIVE_CONFIRMATION_STATE:
            return True
        if state != CONSUMED_CONFIRMATION_STATE:
            return False
        try:
            _write_card_state(
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
                state=ACTIVE_CONFIRMATION_STATE,
                gateway=gateway,
            )
            return True
        except StaleMessageArtifactError:
            continue
        except Exception:  # noqa: BLE001
            break
    logger.warning(
        "A failed run could not restore its consumed card to active",
        conversation_id=conversation_id,
        message_id=message_id,
    )
    return False


def consume_confirmation_for_admitted_run(
    *,
    gateway: Any,
    user_id: str,
    conversation_id: str,
    confirmation_message_id: str | None,
    chat_action: dict[str, Any] | None,
    job_id: str,
    utcnow_iso: Any,
) -> dict[str, Any] | None:
    """Stamp the card consumed the moment its run is admitted.

    Pressing Run is a commitment: the card row is the single source of
    consumption truth, so the stamp lands before dispatch for admitted runs
    and idempotently on replays. When the card changed after the click (a
    guarded edit won the row first), the freshly admitted job is marked
    failed and the run refuses as stale instead of executing values the
    card no longer shows.
    """
    from argus.api.chat.backtest_job_envelopes import admission_rejection_envelope
    from argus.domain.edit_contract_config import in_place_card_edits_enabled

    if not in_place_card_edits_enabled():
        # The in-place surface is dark: no non-turn writer exists, so no
        # stamp is needed and the legacy newer-message clause owns liveness.
        return None
    message_id = str(confirmation_message_id or "").strip()
    if not message_id:
        return None
    clicked_hash = None
    if isinstance(chat_action, dict):
        raw_hash = chat_action.get("launch_payload_hash") or (
            chat_action.get("payload") or {}
        ).get("launch_payload_hash")
        if isinstance(raw_hash, str) and raw_hash.strip():
            clicked_hash = raw_hash.strip()
    consumption = consume_pending_card_for_run(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        expected_launch_payload_hash=clicked_hash,
        gateway=gateway,
    )
    if consumption == "unstamped":
        logger.warning(
            "Run admitted without a consumption stamp; the card row could "
            "not be read, so liveness falls back to the legacy clause",
            conversation_id=conversation_id,
            job_id=job_id,
        )
        return None
    if consumption == "stale_card" and job_id:
        try:
            gateway.mark_backtest_job_failed(
                user_id=user_id,
                job_id=job_id,
                failure_code="confirmation_changed",
                failure_detail=(
                    "The confirmation changed before this run could "
                    "start. Nothing ran."
                ),
                retryable=False,
                finished_at=utcnow_iso(),
                execution_metadata={"refused_before_dispatch": True},
            )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Stale-card run refusal could not mark its job failed",
                job_id=job_id,
                conversation_id=conversation_id,
            )
    if consumption == "stale_card":
        return admission_rejection_envelope("confirmation_changed")
    return None


def restore_pending_card_for_failed_job(
    gateway: Any,
    *,
    user_id: str,
    job: dict[str, Any] | None,
) -> None:
    """A chat run that died without a result gives its card back.

    Research and non-chat jobs carry no confirmation card and fall through.
    Restoration is best-effort and fails toward consumed, never toward a
    wrongly editable card; a missed restore leaves the card dead until the
    user starts over, and the loss is logged by the restorer.
    """
    from argus.domain.backtest_job_lifecycle import (
        JOB_DEAD,
        classify_job_for_card,
    )

    if not isinstance(job, dict):
        return
    if (
        classify_job_for_card(status=job.get("status"), retryable=job.get("retryable"))
        != JOB_DEAD
    ):
        # Only a state no future write can turn into a result gives the
        # card back; may-succeed, has-result, and unknown all fail toward
        # consumed. The worker's success write derives its refusal from
        # the same classification, so the two cannot drift apart.
        return
    if job.get("result_run_id"):
        # A run that produced a result consumed its card for good, whatever
        # its row's status claims; never reactivate it.
        return
    message_id = str(job.get("confirmation_message_id") or "").strip()
    conversation_id = str(job.get("conversation_id") or "").strip()
    if not message_id or not conversation_id:
        return
    restore_pending_card_after_run(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        gateway=gateway,
    )


def apply_pending_card_update(
    *,
    user_id: str,
    conversation_id: str,
    source_message: Any,
    expected_source_metadata: dict[str, Any] | None,
    expected_latest_message_id: str | None,
    confirmation_id: str,
    confirmation_payload: dict[str, Any],
    language: str,
    metadata_extra: dict[str, Any] | None = None,
    runtime_workflow: Any | None = None,
):
    """The only write path for a non-turn change to a pending confirmation.

    The edit contract's dividing line is whether a turn was spent, not which
    affordance asked. A turn-based edit mints a new card because the
    conversation records the change; a non-turn change spent nothing, so the
    card it changed is the record, rewritten in place: same confirmation id,
    same message, nothing appended. Every non-turn producer must write
    through here; a key set to None in ``metadata_extra`` is removed so a
    consumed sidecar cannot go stale on the updated card.

    The write is conditional on what the caller read:
    ``expected_source_metadata`` guards the card's own row, and
    ``expected_latest_message_id`` guards conversation activity, because
    every superseding event (a turn, a run result, a cancellation) appends
    a message while a non-turn edit appends nothing, so an interleaved
    append means the caller's active-confirmation check may no longer hold.
    A concurrent writer raises ``StaleMessageArtifactError`` instead of
    being silently rolled back, and callers surface that as a conflict; a
    retry re-reads and re-checks. The rewritten card also carries its
    projections: the conversation's denormalized preview follows the card
    when it is the latest message, and when a runtime checkpoint exists its
    pending strategy, active reference, and confirmation payload are
    rewritten to the edited card. Without the checkpoint sync, a later turn
    whose metadata fallback carries no snapshot reads the pre-edit strategy
    from the checkpoint, and correctness depends on a caller remembering the
    fallback. Returns the updated message, or None when the card cannot be
    assembled.
    """
    from argus.agent_runtime.confirmation_artifacts import (
        confirmation_artifact_reference,
    )
    from argus.agent_runtime.stages.artifact_context import confirmation_card_is_dead
    from argus.api.message_store import message_preview, update_message_artifact

    # The write-path invariant: no confirmation card is mutated after its
    # run has been admitted (or it was cancelled or superseded). Enforced
    # here so every producer, present or future, inherits it; the guarded
    # write's metadata compare keeps this check honest against races.
    if confirmation_card_is_dead(source_message.metadata) or (
        expected_source_metadata is not None
        and confirmation_card_is_dead(expected_source_metadata)
    ):
        raise DeadConfirmationCardError(
            "The confirmation is no longer pending; nothing was written."
        )

    confirmation_payload["confirmation_id"] = confirmation_id
    confirmation_payload["artifact_id"] = confirmation_id
    card = runtime_confirmation_card(
        {
            "stage_outcome": "await_approval",
            "confirmation_payload": confirmation_payload,
        },
        confirmation_id=confirmation_id,
        conversation_id=conversation_id,
        language=language,
    )
    if card is None:
        return None
    reference = confirmation_artifact_reference(
        confirmation_id=confirmation_id,
        confirmation_payload=confirmation_payload,
        confirmation_card=card,
    )
    metadata: dict[str, Any] = {
        **source_message.metadata,
        "conversation_mode": "confirm",
        "agent_runtime_stage_outcome": "await_approval",
        "confirmation_card": card,
        "confirmation_payload": confirmation_payload,
        "active_confirmation_reference": reference.model_dump(mode="python"),
        "artifact_references": [reference.model_dump(mode="python")],
    }
    for key, value in (metadata_extra or {}).items():
        if value is None:
            metadata.pop(key, None)
        else:
            metadata[key] = value
    content = str(card.get("summary") or "")
    updated = update_message_artifact(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=source_message.id,
        content=content,
        metadata=metadata,
        expected_source_metadata=expected_source_metadata,
        expected_latest_message_id=expected_latest_message_id,
        preview=message_preview(
            content, role=str(source_message.role), metadata=metadata
        ),
    )
    if runtime_workflow is not None:
        _sync_runtime_checkpoint_with_card(
            workflow=runtime_workflow,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=source_message.id,
            confirmation_payload=confirmation_payload,
            reference=reference,
        )
    return updated


def _persisted_card_message(
    *,
    user_id: str,
    conversation_id: str,
    message_id: str,
) -> Any | None:
    """Fresh read of the persisted card, for post-sync verification only."""
    from argus.api import state as api_state

    gateway = api_state.supabase_gateway
    if gateway is not None:
        try:
            message = gateway.get_message(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )
            if message is not None:
                return message
        except Exception:  # noqa: BLE001
            pass
    with api_state.store.conversation_message_lock:
        for existing in api_state.store.messages.get(conversation_id, []):
            if existing.id == message_id:
                return existing
    return None


# One process-wide lock serializes checkpoint syncs. Edits are rare user
# actions and a sync is a few checkpointer round trips, so cross-conversation
# contention is negligible and a single lock avoids an unbounded per-key map.
_CHECKPOINT_SYNC_LOCK = threading.Lock()


def _sync_runtime_checkpoint_with_card(
    *,
    workflow: Any,
    user_id: str,
    conversation_id: str,
    message_id: str,
    confirmation_payload: dict[str, Any],
    reference: Any,
) -> None:
    """Rewrite the checkpoint's view of the pending card to the edited one.

    Best-effort by design: the persisted message is the durable truth and the
    metadata fallback still corrects a missed sync, so a checkpoint write
    failure degrades to the old conditional behaviour instead of failing the
    edit. The failure is logged loudly because it reintroduces the two-source
    drift this sync exists to close.

    Guarded writes serialize the persisted card, but the checkpoint write
    happens after it, so winners could sync out of order. Syncs for a
    process are serialized by a module lock, and after every checkpoint
    write the sync re-reads the persisted card and repeats until the
    payload it wrote is still the durable one, bounded at three passes. The
    checkpointer offers no compare-and-set, so a cross-process interleave
    inside the final read-to-write window can still stale the checkpoint;
    that residue is detected and logged, and the next turn's metadata
    fallback corrects it.
    """
    import asyncio

    from argus.agent_runtime.state.models import (
        ConfirmationPayload,
        StrategySummary,
        TaskSnapshot,
    )

    async def _write(payload: dict[str, Any], active_reference: Any) -> bool:
        config = {"configurable": {"thread_id": conversation_id}}
        state = await workflow.aget_state(config)
        values = getattr(state, "values", None)
        if not isinstance(values, dict) or not values:
            return False
        strategy = StrategySummary.model_validate(payload["strategy"])
        updates: dict[str, Any] = {
            "confirmation_payload": dict(payload),
        }
        snapshot = values.get("latest_task_snapshot")
        if isinstance(snapshot, dict):
            snapshot = TaskSnapshot.model_validate(snapshot)
        if isinstance(snapshot, TaskSnapshot):
            updates["latest_task_snapshot"] = snapshot.model_copy(
                update={
                    "pending_strategy_summary": strategy,
                    "active_confirmation_reference": active_reference,
                }
            )
        run_state = values.get("run_state")
        if run_state is not None:
            updates["run_state"] = run_state.model_copy(
                update={
                    "candidate_strategy_draft": strategy,
                    "confirmation_payload": ConfirmationPayload.model_validate(payload),
                }
            )
        # The write is attributed to the terminal node so a resumed graph
        # never re-enters mid-flight; each turn starts fresh from its input.
        from argus.agent_runtime.graph.workflow import WorkflowNode

        await workflow.aupdate_state(
            config, updates, as_node=WorkflowNode.NEXT_STEP.value
        )
        return True

    def _durable_payload() -> tuple[dict[str, Any], dict[str, Any]] | None:
        persisted = _persisted_card_message(
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
        metadata = getattr(persisted, "metadata", None)
        if not isinstance(metadata, dict):
            return None
        payload = metadata.get("confirmation_payload")
        if not isinstance(payload, dict):
            return None
        return payload, metadata

    async def _sync() -> None:
        wrote = await _write(confirmation_payload, reference)
        if not wrote:
            return
        from argus.agent_runtime.confirmation_artifacts import (
            confirmation_artifact_reference,
        )

        written = confirmation_payload
        for _ in range(3):
            durable = _durable_payload()
            if durable is None or durable[0] == written:
                return
            persisted_payload, metadata = durable
            persisted_reference = confirmation_artifact_reference(
                confirmation_id=str(persisted_payload.get("confirmation_id") or ""),
                confirmation_payload=persisted_payload,
                confirmation_card=(
                    metadata.get("confirmation_card")
                    if isinstance(metadata.get("confirmation_card"), dict)
                    else None
                ),
            )
            await _write(persisted_payload, persisted_reference)
            written = persisted_payload
        durable = _durable_payload()
        if durable is not None and durable[0] != written:
            logger.warning(
                "Checkpoint convergence exhausted its passes; the checkpoint "
                "may trail the persisted card until the next turn's fallback",
                conversation_id=conversation_id,
            )

    try:
        with _CHECKPOINT_SYNC_LOCK:
            asyncio.run(_sync())
    except Exception:
        logger.opt(exception=True).warning(
            "In-place card edit could not sync the runtime checkpoint; a "
            "fallback-less turn may read the pre-edit strategy",
            conversation_id=conversation_id,
        )


def attach_research_peer_rows(
    runtime_result: dict[str, Any],
    metadata: dict[str, Any],
    *,
    user_id: str,
    conversation_id: str,
    language: str,
) -> None:
    """Attach remaining researched peers as Try-next rows on a card turn.

    Peers come from the persisted research sidecar, not runtime state: inline
    turns, the dev synchronous fallback, and the background job finalizer all
    persist the same sidecar, so the transcript is the one contract every
    completion path already honors."""
    if not isinstance(runtime_result.get("confirmation_payload"), dict):
        return
    from argus.domain.research.config import research_rail_enabled

    if not research_rail_enabled():
        return
    strategy = runtime_result["confirmation_payload"].get("strategy")
    if not isinstance(strategy, dict):
        return
    peers = research_peers_from_transcript(
        user_id=user_id,
        conversation_id=conversation_id,
        basket_symbols=[
            str(symbol).strip().upper()
            for symbol in strategy.get("asset_universe") or []
            if str(symbol).strip()
        ],
    )
    rows = research_peer_add_rows_for_confirmation(
        peers,
        confirmation_payload=runtime_result["confirmation_payload"],
        language=language,
    )
    if rows is not None:
        metadata["next_experiments"] = rows
        runtime_result["next_experiments"] = rows


def research_peers_from_transcript(
    *,
    user_id: str,
    conversation_id: str,
    basket_symbols: list[str],
    limit: int = 20,
) -> list[dict[str, Any]]:
    """The most recent research about these assets decides the peers.

    Newest-first over the persisted transcript, the first research sidecar
    whose anchors or peers overlap the basket wins; unrelated research in
    between neither offers its peers here nor hides the relevant ones. An
    empty peer list on the winning sidecar is honest truth, not a miss."""
    basket = {symbol for symbol in basket_symbols if symbol}
    if not basket:
        return []
    from argus.api.chat.recovery import _recent_messages_for_conversation

    try:
        messages = _recent_messages_for_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=limit,
        )
    except Exception:  # noqa: BLE001
        messages = []
    for message in reversed(messages):
        if message.role != "assistant" or not isinstance(message.metadata, dict):
            continue
        sidecar = message.metadata.get("research")
        if not isinstance(sidecar, dict):
            continue
        peers = [p for p in sidecar.get("peers") or [] if isinstance(p, dict)]
        anchors = {
            str(symbol).strip().upper()
            for symbol in sidecar.get("anchor_symbols") or []
            if str(symbol).strip()
        }
        peer_symbols = {str(p.get("symbol") or "").strip().upper() for p in peers} - {""}
        if basket & (anchors | peer_symbols):
            return peers
    return []


def research_peer_add_rows_for_confirmation(
    peers: list[dict[str, Any]],
    *,
    confirmation_payload: dict[str, Any],
    language: str,
) -> dict[str, Any] | None:
    """Researched peers still outside the basket ride the ordinary Try-next
    surface below the card's turn; composition lives with the materializer."""
    from argus.domain.research.config import research_rail_enabled

    if not research_rail_enabled():
        return None
    if not peers:
        return None
    strategy = confirmation_payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    from argus.agent_runtime.research_basket import peer_add_rows

    return peer_add_rows(
        peers,
        basket_symbols=[
            str(symbol).strip().upper()
            for symbol in strategy.get("asset_universe") or []
            if str(symbol).strip()
        ],
        basket_asset_class=str(strategy.get("asset_class") or "equity"),
        language=language,
    )


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
    return {
        "code": "effective_window_adjusted",
        "requested_date_range": dict(requested),
        "effective_date_range": dict(effective),
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


def _confirmation_display_capital(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
    strategy_type: str,
) -> float | None:
    strategy_capital = _numeric_money_value(strategy.get("capital_amount"))
    if _strategy_type_uses_cadence(strategy_type):
        return strategy_capital
    return (
        strategy_capital
        or _numeric_money_value(
            _optional_parameter_value(optional_parameters, "initial_capital")
        )
        or _numeric_money_value(launch_payload.get("capital_amount"))
        or _numeric_money_value(launch_payload.get("starting_capital"))
    )


def _confirmation_dca_starting_capital(optional_parameters: dict[str, Any]) -> float:
    """The seed the card shows. Only a stated one counts; the default is $0."""
    entry = optional_parameters.get("initial_capital")
    if not isinstance(entry, dict) or str(entry.get("source") or "") != "user":
        return 0.0
    value = entry.get("value")
    if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
        return 0.0
    return float(value)


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


def _numeric_money_value(value: Any) -> float | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    amount = float(value)
    return amount if amount > 0 else None


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


def _confirmation_assumptions(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any] | None = None,
    language: str = "en",
) -> list[str]:
    assumptions: list[str] = []
    strategy_type = executable_strategy_type(strategy)
    strategy_capital = strategy.get("capital_amount")
    if _strategy_type_uses_cadence(strategy_type):
        # The strip follows the card's two rows, in the same order and with
        # the same two roles.
        assumptions.append(
            _money_assumption(
                _confirmation_dca_starting_capital(optional_parameters),
                role="starting_capital",
            )
        )
        if isinstance(strategy_capital, int | float):
            assumptions.append(
                _contribution_assumption(
                    float(strategy_capital),
                    strategy=strategy,
                )
            )
    elif isinstance(strategy_capital, int | float):
        assumptions.append(
            _money_assumption(
                float(strategy_capital),
                role="starting_capital",
            )
        )
    else:
        initial_capital = _optional_parameter_value(
            optional_parameters, "initial_capital"
        )
        if isinstance(initial_capital, int | float):
            assumptions.append(
                _money_assumption(
                    float(initial_capital),
                    role="starting_capital",
                )
            )
    timeframe = _optional_parameter_value(optional_parameters, "timeframe")
    if timeframe:
        assumptions.append(format_timeframe_data_label(timeframe, language=language))
    data_through_assumption = _data_through_assumption(strategy, language=language)
    if data_through_assumption:
        assumptions.append(data_through_assumption)
    execution_costs = _confirmation_execution_costs(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload or {},
    )
    if execution_costs is not None:
        assumptions.append(_execution_cost_assumption(execution_costs))
    # No prose for the zero-cost case: `display_facts` already carries `fees`
    # and `slippage` whenever they are zero, and the card localizes them from
    # there. A second English copy of the same fact is what put "No fees" on a
    # Spanish card (#434).
    benchmark_assumption = _confirmation_benchmark_assumption(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload or {},
    )
    if benchmark_assumption:
        assumptions.append(benchmark_assumption)
    return assumptions


def _data_through_assumption(
    strategy: dict[str, Any],
    *,
    language: str,
) -> str | None:
    adjustment = _data_availability_adjustment(strategy)
    if adjustment is None:
        return None
    return format_data_through_label(adjustment.get("through"), language=language) or None


def _confirmation_display_facts(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    timeframe = _optional_parameter_value(optional_parameters, "timeframe")
    if timeframe:
        facts["timeframe"] = timeframe
    data_adjustment = _data_availability_adjustment(strategy)
    if data_adjustment is not None:
        facts["data_through"] = data_adjustment.get("through")
    execution_costs = _confirmation_execution_costs(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
    )
    if execution_costs is not None:
        facts["fees"] = execution_costs["fees"]
        facts["slippage"] = execution_costs["slippage"]
    else:
        fees = _optional_parameter_value(optional_parameters, "fees")
        if fees is not None:
            facts["fees"] = fees
        slippage = _optional_parameter_value(optional_parameters, "slippage")
        if slippage is not None:
            facts["slippage"] = slippage
    benchmark_symbol = _confirmation_benchmark_symbol(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
    )
    if benchmark_symbol:
        facts["benchmark_symbol"] = benchmark_symbol
    return facts


def _data_availability_adjustment(strategy: dict[str, Any]) -> dict[str, Any] | None:
    extra_parameters = strategy.get("extra_parameters")
    if not isinstance(extra_parameters, dict):
        return None
    adjustment = extra_parameters.get("data_availability_adjustment")
    if not isinstance(adjustment, dict):
        return None
    if adjustment.get("kind") not in {
        "latest_complete_daily_data",
        "latest_complete_market_data",
    }:
        return None
    through = adjustment.get("through")
    if not isinstance(through, str):
        return None
    if not _data_adjustment_matches_strategy_end(strategy, through=through):
        return None
    return adjustment


def _data_adjustment_matches_strategy_end(
    strategy: dict[str, Any],
    *,
    through: str,
) -> bool:
    date_range = strategy.get("date_range")
    if not isinstance(date_range, dict):
        return True
    end = date_range.get("end") or date_range.get("to")
    return end in (None, "") or str(end) == through


def _confirmation_benchmark_assumption(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
) -> str | None:
    symbol = _confirmation_benchmark_symbol(
        strategy=strategy,
        optional_parameters=optional_parameters,
        launch_payload=launch_payload,
    )
    return _benchmark_assumption(symbol) if symbol else None


def _confirmation_benchmark_symbol(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
) -> str | None:
    for value in (
        strategy.get("comparison_baseline"),
        strategy.get("benchmark_symbol"),
        _optional_parameter_value(optional_parameters, "benchmark_symbol"),
        launch_payload.get("benchmark_symbol"),
    ):
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    asset_class = strategy.get("asset_class")
    if asset_class == "crypto":
        return "BTC"
    if asset_class == "equity":
        return "SPY"
    return None


def _confirmation_execution_costs(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
    launch_payload: dict[str, Any],
) -> dict[str, float] | None:
    if not _execution_realism_feature_enabled():
        # With the engine flag off the run is idealized no matter what values a
        # draft carries, so never advertise modeled costs.
        return None

    launch_realism = launch_payload.get("_execution_realism")
    if isinstance(launch_realism, dict):
        try:
            realism = _normalize_execution_realism(launch_realism)
        except ValueError:
            realism = {"enabled": False, "fee_bps": 0.0, "slippage_bps": 0.0}
    else:
        realism = {"enabled": False, "fee_bps": 0.0, "slippage_bps": 0.0}
    if bool(realism["enabled"]):
        costs = {
            "fees": float(realism["fee_bps"]) / 10000.0,
            "slippage": float(realism["slippage_bps"]) / 10000.0,
        }
        if costs["fees"] > 0.0 or costs["slippage"] > 0.0:
            return costs

    extra_parameters = strategy.get("extra_parameters")
    if isinstance(extra_parameters, dict):
        costs = {
            "fees": _optional_float(extra_parameters.get("fee_rate")) or 0.0,
            "slippage": _optional_float(extra_parameters.get("slippage")) or 0.0,
        }
        if costs["fees"] > 0.0 or costs["slippage"] > 0.0:
            return costs

    costs = {
        "fees": _optional_float(_optional_parameter_value(optional_parameters, "fees"))
        or 0.0,
        "slippage": _optional_float(
            _optional_parameter_value(optional_parameters, "slippage")
        )
        or 0.0,
    }
    if costs["fees"] > 0.0 or costs["slippage"] > 0.0:
        return costs
    return None


def _execution_cost_assumption(costs: dict[str, float]) -> str:
    fee_bps = _format_bps(float(costs["fees"]) * 10000.0)
    slippage_bps = _format_bps(float(costs["slippage"]) * 10000.0)
    return f"Modeled costs: {fee_bps} bps fee + {slippage_bps} bps slippage"


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_bps(value: float) -> str:
    rounded = round(value, 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:g}"


# The card's prose fields are English by design: the frontend localizes from
# the typed fields beside them (`status`, `strategy_type`,
# `rows[].key`/`labelKey`, `display_facts`), and these strings stay as
# persisted-card and old-client compatibility
# (`docs/CONVERSATIONAL_RUNTIME.md` forbids per-language copy in the runtime).
# `summary` embeds the language-formatted period and becomes the card
# message's persisted content, which feeds `last_message_preview`.
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


def _optional_parameter_value(optional_parameters: dict[str, Any], key: str) -> Any:
    value = optional_parameters.get(key)
    if isinstance(value, dict):
        return value.get("value")
    return None


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


def _strategy_type_uses_cadence(strategy_type: str) -> bool:
    normalized = strategy_type.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {
        "dca",
        "dca_accumulation",
        "recurring_accumulation",
        "recurring_buys",
    }


def _article_for(value: str) -> str:
    return "an" if value[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _confirmation_title(*, assets: str, strategy_type: str) -> str:
    return f"{assets} {strategy_type}".strip()


def _confirmation_status_label(*, is_ready_to_run: bool) -> str:
    return "Ready to run" if is_ready_to_run else "Needs change"


def _money_assumption(value: float, *, role: str) -> str:
    label = (
        "recurring contribution"
        if role == "recurring_contribution"
        else "starting capital"
    )
    return f"${value:,.0f} {label}"


def _contribution_assumption(amount: float, *, strategy: dict[str, Any]) -> str:
    return f"{_contribution_row_value(amount, strategy=strategy)} contribution"


def _benchmark_assumption(symbol: str) -> str:
    return f"Benchmark: {symbol}"


def _confirmation_today() -> date:
    return date.today()
