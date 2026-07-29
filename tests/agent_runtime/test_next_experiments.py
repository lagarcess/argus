"""Stage-0 Try next selection (issue #249, spec
2026-07-29-try-next-surface-ownership.md): deterministic, result-aware,
capped, typed — and attached to the completed-result stage patch."""

from __future__ import annotations

from argus.agent_runtime.next_experiments import (
    NEXT_EXPERIMENT_ACTION_LABELS,
    NEXT_EXPERIMENTS_ROW_CAP,
    NEXT_EXPERIMENTS_VERSION,
    next_experiments_sidecar,
)
from argus.agent_runtime.stages.explain import explain_stage
from argus.agent_runtime.state.models import ResponseProfile, RunState

_BUY_AND_HOLD_FACTS = {"config_snapshot": {"template": "buy_and_hold"}, "symbols": ["AAPL"]}


def test_sidecar_caps_rows_and_carries_typed_identity() -> None:
    sidecar = next_experiments_sidecar(_BUY_AND_HOLD_FACTS)

    assert sidecar is not None
    assert sidecar["version"] == NEXT_EXPERIMENTS_VERSION
    assert 1 <= len(sidecar["rows"]) <= NEXT_EXPERIMENTS_ROW_CAP
    for row in sidecar["rows"]:
        assert row["kind"]
        assert row["label"]
        assert row["label_key"] == f"chat.next_experiments.labels.{row['kind']}"


def test_losing_run_leads_with_refinement_and_says_why() -> None:
    sidecar = next_experiments_sidecar(
        _BUY_AND_HOLD_FACTS,
        total_return=5.0,
        benchmark_return=12.5,
    )

    assert sidecar is not None
    first = sidecar["rows"][0]
    assert first["kind"] in {
        "supported_rsi_threshold",
        "supported_ma_crossover",
        "compare_buy_and_hold",
    }
    assert first["why"] == {
        "code": "lost_to_benchmark",
        "params": {"points": 7.5},
    }


def test_winning_run_leads_with_exploration() -> None:
    sidecar = next_experiments_sidecar(
        _BUY_AND_HOLD_FACTS,
        total_return=20.0,
        benchmark_return=8.0,
    )

    assert sidecar is not None
    first = sidecar["rows"][0]
    assert first["kind"] in {"change_date_range", "same_setup_peer_asset"}
    assert first["why"]["code"] == "beat_benchmark"


def test_deep_drawdown_outranks_the_benchmark_story() -> None:
    sidecar = next_experiments_sidecar(
        _BUY_AND_HOLD_FACTS,
        total_return=20.0,
        benchmark_return=8.0,
        max_drawdown=-22.4,
    )

    assert sidecar is not None
    assert sidecar["rows"][0]["kind"] in {
        "supported_rsi_threshold",
        "supported_ma_crossover",
        "compare_buy_and_hold",
    }
    assert sidecar["rows"][0]["why"] == {
        "code": "deep_drawdown",
        "params": {"drawdown": -22.4},
    }


def test_every_offered_kind_has_labels_in_both_languages() -> None:
    for family in (
        {"config_snapshot": {"template": "buy_and_hold"}},
        {"config_snapshot": {"template": "indicator_threshold"}},
        {"config_snapshot": {"template": "signal_strategy"}},
        {"config_snapshot": {"template": "dca_accumulation"}},
        {"config_snapshot": {}},
    ):
        sidecar = next_experiments_sidecar(family)
        assert sidecar is not None
        for row in sidecar["rows"]:
            for language in ("en", "es-419"):
                assert row["label_key"] in NEXT_EXPERIMENT_ACTION_LABELS[language]


def test_explain_stage_attaches_the_sidecar_to_the_result_patch() -> None:
    state = RunState.new(current_user_message="why", recent_thread_history=[])
    state.effective_response_profile = ResponseProfile(
        effective_tone="concise",
        effective_verbosity="low",
        effective_expertise_mode="advanced",
    )
    state.confirmation_payload = {
        "strategy": {"strategy_thesis": "Buy Tesla on pullbacks"},
        "optional_parameters": {},
    }
    state.final_response_payload = {
        "result": {"total_return": 0.14, "benchmark_return": 0.09}
    }

    result = explain_stage(state=state)

    sidecar = result.patch["next_experiments"]
    assert sidecar["version"] == NEXT_EXPERIMENTS_VERSION
    assert 1 <= len(sidecar["rows"]) <= NEXT_EXPERIMENTS_ROW_CAP


def test_rows_never_reoffer_what_the_conversation_already_asked() -> None:
    sidecar = next_experiments_sidecar(
        _BUY_AND_HOLD_FACTS,
        recent_user_messages=[
            "Test AAPL for all of 2023 with $1000.",
            "Test a different date range",
            "  probar el mismo enfoque en un activo similar  ",
        ],
    )

    assert sidecar is not None
    kinds = [row["kind"] for row in sidecar["rows"]]
    assert "change_date_range" not in kinds
    assert "same_setup_peer_asset" not in kinds
    assert kinds
