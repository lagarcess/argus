"""The promotion-walk cases share without model/provider calls."""

import pytest
from argus.api import public_excerpts as service
from argus.api import state as api_state
from argus.domain.public_excerpts import PublicExcerptSourceError

from tests.test_public_excerpt_turns import (
    add_pair,
    create,
    preview,
    seed_backtest,
)
from tests.test_public_excerpt_turns import owner as owner_fixture


@pytest.fixture
def owner(monkeypatch):
    return owner_fixture.__wrapped__(monkeypatch)


PUBLISHER_LINK = (
    "See [Coca-Cola second-quarter results]("
    "https://investors.coca-colacompany.com/news-events/press-releases/detail/"
    "1112/coca-cola-reports-second-quarter-2024-results-and-raises-full-year-guidance)."
)


@pytest.mark.parametrize(
    "surface",
    [
        "quick_take",
        "breakdown",
        "follow_up",
        "long_research",
        "memory",
        "degraded",
        "plain",
    ],
)
def test_promotion_answers_share_as_the_owner_previewed(owner, surface):
    question, answer = add_pair(owner)
    if surface in {"quick_take", "breakdown"}:
        answer.content = PUBLISHER_LINK
    elif surface == "follow_up":
        answer.metadata["research"]["sources"] = []
    elif surface == "long_research":
        question.content = "A detailed question. " * 30
        answer.content = "A detailed answer. " * 250
    elif surface == "memory":
        answer.metadata["memory_recalls"] = [{"hidden": "Never add this to the receipt"}]
    elif surface == "degraded":
        answer.metadata["research"]["degraded"] = True
    else:
        answer.metadata.pop("research")
    shown = preview(owner, [answer])
    leaf = shown.payload.turns[0]
    assert leaf.question == question.content
    assert leaf.answer == answer.content
    saved, made = create(owner, [answer], shown)
    assert made and saved.payload == shown.payload
    assert "Never add this" not in saved.payload.model_dump_json()


@pytest.mark.parametrize("marker", ["confirmation", "confirmation_card", "clarification"])
def test_confirmation_and_clarification_are_not_selection_units(owner, marker):
    _, pending = add_pair(
        owner,
        metadata={
            marker: {},
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
        },
    )
    assert (
        service.receipt_candidates(user=owner[0], conversation_id=owner[1].id).items == []
    )
    with pytest.raises(PublicExcerptSourceError):
        preview(owner, [pending])


def test_finished_backtest_keeps_question_and_visible_answer(owner):
    _, _, answer = seed_backtest(owner)
    answer.content = PUBLISHER_LINK
    shown = preview(owner, [answer])
    assert shown.payload.turns[0].answer == answer.content
    assert (
        shown.payload.turns[0].question
        == api_state.store.messages[owner[1].id][0].content
    )


def test_only_final_answer_in_a_turn_is_selectable(owner):
    _, intermediate = add_pair(owner)
    final = intermediate.model_copy(
        update={"id": api_state.store.new_id(), "content": "The final answer."}
    )
    from tests.public_excerpt_factories import utc

    final.created_at = utc(2)
    api_state.store.messages[owner[1].id].append(final)
    candidates = service.receipt_candidates(user=owner[0], conversation_id=owner[1].id)
    assert [candidate.message_id for candidate in candidates.items] == [final.id]
    with pytest.raises(PublicExcerptSourceError):
        preview(owner, [intermediate])
    assert preview(owner, [final]).payload.turns[0].answer == final.content


def seed_direct_backtest(owner, *, status="succeeded", dca=False):
    from copy import deepcopy

    from tests.public_excerpt_factories import GENERATED_CARD_CONFIG_SNAPSHOT

    artifact, run, answer = seed_backtest(owner)
    run.conversation_result_card.update(
        evidence_artifact_id=artifact.id,
        idea_id=artifact.idea_id,
        idea_version_id=artifact.idea_version_id,
    )
    # The completed direct-action message in the retained owner-scoped gateway
    # diagnosis has run/card identity but no job id or agent terminal envelope.
    answer.metadata = {
        "result_run_id": run.id,
        "latest_run_id": run.id,
        "result_card": run.conversation_result_card,
        "conversation_mode": "result_review",
        "chat_action": {"type": "run_backtest"},
    }
    job_id = api_state.store.new_id()
    api_state.store.backtest_jobs[job_id] = {
        "id": job_id,
        "user_id": owner[0].id,
        "conversation_id": owner[1].id,
        "operation_scope": "chat.run_backtest",
        "status": status,
        "result_run_id": run.id,
        "request_message_id": api_state.store.messages[owner[1].id][0].id,
    }
    if dca:
        run.config_snapshot.update(deepcopy(GENERATED_CARD_CONFIG_SNAPSHOT))
        # engine_launch.adapter._execute_dca freezes cadence on entry_rule.
        run.config_snapshot["resolved_strategy"]["entry_rule"] = {
            "type": "periodic_accumulation",
            "cadence": "monthly",
        }
    return run, answer


@pytest.mark.parametrize("dca", [False, True], ids=["buy_hold", "dca"])
def test_direct_finished_result_uses_its_canonical_completed_job(owner, dca):
    run, answer = seed_direct_backtest(owner, dca=dca)
    shown = preview(owner, [answer])
    leaf = shown.payload.turns[0]
    assert leaf.kind == "backtest"
    assert leaf.answer == answer.content
    if dca:
        assert (
            leaf.fact_bank.config_snapshot.resolved_strategy.entry_rule.cadence
            == "monthly"
        )
    assert create(owner, [answer], shown)[0].payload == shown.payload


@pytest.mark.parametrize("status", ["queued", "running", "failed"])
def test_direct_result_does_not_override_unsettled_canonical_job(owner, status):
    _, answer = seed_direct_backtest(owner, status=status)
    with pytest.raises(PublicExcerptSourceError) as error:
        preview(owner, [answer])
    assert error.value.reason == "not_completed"


def test_followup_keeps_its_own_question_and_does_not_add_the_referenced_run(owner):
    run, _ = seed_direct_backtest(owner)
    question, answer = add_pair(
        owner,
        index=3,
        question="What does that return mean?",
        metadata={
            "agent_runtime_turn": {"terminal": True, "status": "completed"},
            "result_run_id": run.id,
        },
    )
    leaf = preview(owner, [answer]).payload.turns[0]
    assert leaf.kind == "answer"
    assert leaf.question == question.content
    assert leaf.answer == answer.content
    assert "fact_bank" not in leaf.model_dump()


@pytest.mark.parametrize("missing", ["job", "artifact", "identity"])
def test_direct_result_without_a_job_uses_canonical_owned_run_readability(owner, missing):
    run, answer = seed_direct_backtest(owner)
    api_state.store.backtest_jobs.clear()
    if missing == "artifact":
        api_state.store.evidence_artifacts.clear()
    elif missing == "identity":
        run.conversation_result_card.pop("idea_version_id")
    if missing == "job":
        assert preview(owner, [answer]).payload.turns[0].kind == "backtest"
    else:
        with pytest.raises(PublicExcerptSourceError) as error:
            preview(owner, [answer])
        assert error.value.reason == "not_completed"


def test_private_unproven_calculation_inputs_remain_unpublishable(owner):
    from tests.domain.calculations import WORKED_ARGUMENTS
    from tests.test_public_excerpt_calculation_turns import add_calculation

    answer, _ = add_calculation(
        owner, kind="ranked_comparison", arguments=WORKED_ARGUMENTS["ranked_comparison"]
    )
    for fact in answer.metadata["tool_result_cards"][0]["presentation"]["inputs"]:
        fact["source"] = None
        fact["visibility"] = "private"
    with pytest.raises(PublicExcerptSourceError) as error:
        preview(owner, [answer])
    assert error.value.reason == "private_inputs"


def test_dca_public_facts_accept_the_real_adapter_rule_shape(owner, monkeypatch):
    from types import SimpleNamespace

    from argus.domain.engine_launch import adapter
    from argus.domain.engine_launch.models import LaunchBacktestRequest

    from tests.public_excerpt_factories import WINDOW_END, WINDOW_START

    run, answer = seed_direct_backtest(owner, dca=True)
    request = LaunchBacktestRequest(
        strategy_type="dca_accumulation",
        symbol=run.symbols[0],
        timeframe="1D",
        date_range={"start": WINDOW_START, "end": WINDOW_END},
        sizing_mode="capital_amount",
        capital_amount=200,
        starting_capital=1000,
        cadence="monthly",
        benchmark_symbol=run.benchmark_symbol,
    )
    monkeypatch.setattr(
        adapter,
        "classify_symbol",
        lambda symbol: SimpleNamespace(
            canonical_symbol=symbol, symbol=symbol, asset_class="equity"
        ),
    )
    monkeypatch.setattr(
        adapter, "_prepared_market_data_for_request", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(adapter, "_initial_price", lambda *args, **kwargs: 100)
    monkeypatch.setattr(
        adapter, "compute_alpha_metrics", lambda *args, **kwargs: run.metrics
    )
    monkeypatch.setattr(
        adapter, "build_result_card", lambda *args, **kwargs: run.conversation_result_card
    )
    monkeypatch.setattr(adapter, "build_result_chart", lambda *args, **kwargs: run.chart)
    generated = adapter.run_launch_backtest(request).envelope
    assert generated.execution_status == "succeeded"
    run.config_snapshot.update(
        resolved_strategy=generated.resolved_strategy,
        resolved_parameters=generated.resolved_parameters,
    )
    leaf = preview(owner, [answer]).payload.turns[0]
    assert (
        leaf.fact_bank.config_snapshot.resolved_strategy.entry_rule.model_dump(
            exclude_none=True
        )
        == generated.resolved_strategy["entry_rule"]
    )
    assert (
        leaf.fact_bank.config_snapshot.resolved_parameters.recurring_contribution
        == request.recurring_contribution
    )


def test_public_source_names_do_not_trigger_internal_metadata_heuristics(owner):
    _, answer = add_pair(owner)
    answer.metadata["research"]["sources"][0].update(
        title="OpenRouter company announcement",
        url="https://openrouter.ai/announcement",
        domain="openrouter.ai",
    )
    leaf = preview(owner, [answer]).payload.turns[0]
    assert leaf.sources[0].url == answer.metadata["research"]["sources"][0]["url"]
