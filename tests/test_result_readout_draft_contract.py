"""Declared run references stay grounded without per-occurrence bookkeeping."""

import pytest
from argus.domain.result_readout_grounding import accepted_readout_text


@pytest.fixture
def fact_sheet():
    values = {
        "portfolio.total_return": (15.126, "percent"),
        "portfolio.annualized_return": (6.846, "percent"),
        "portfolio.annualized_volatility": (28.567, "percent"),
        "portfolio.executed_fills": (13, "count"),
        "portfolio.max_drawdown": (-31.234, "percent"),
        "portfolio.profit": (1234.56, "currency"),
        "window.start": ("2023-09-01", "date"),
    }
    return {
        "facts": {
            key: {"value": value, "unit": unit}
            for key, (value, unit) in values.items()
        }
    }


def figure(key, value):
    return {"fact_key": key, "value": value}


def draft(text, figures=(), language="en"):
    return {"language": language, "text": text, "figures": list(figures)}


@pytest.mark.parametrize("language", ["en", "es-419"])
@pytest.mark.parametrize(
    "key,value",
    [
        ("portfolio.annualized_return", 6.8),
        ("portfolio.annualized_volatility", 28.57),
        ("portfolio.executed_fills", 13),
        ("portfolio.profit", 1235),
        ("window.start", "2023-09-01"),
    ],
)
def test_declared_reference_accepts_stored_value_with_display_rounding(
    fact_sheet, language, key, value
):
    response = draft(f"{value}.", [figure(key, value)], language)
    assert accepted_readout_text(response, facts=fact_sheet, language=language) == (
        response["text"], None
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("unknown.fact", 6.8),
        ("portfolio.total_return", 6.8),
        ("portfolio.annualized_return", 15.1),
        ("portfolio.executed_fills", 12),
        ("portfolio.profit", 1234),
        ("window.start", "2023-10-01"),
    ],
)
def test_false_or_unknown_declared_reference_rejects_complete_draft(
    fact_sheet, key, value
):
    assert accepted_readout_text(
        draft(f"{value}.", [figure(key, value)]), facts=fact_sheet, language="en"
    ) == (None, "invalid_figure_reference")


@pytest.mark.parametrize("language", ["en", "es-419"])
def test_repeated_fill_count_needs_only_one_reference(fact_sheet, language):
    text = (
        "13 executed fills, not 13 completed round trips."
        if language == "en"
        else "13 ejecuciones, no 13 operaciones completas."
    )
    assert accepted_readout_text(
        draft(text, [figure("portfolio.executed_fills", 13)], language),
        facts=fact_sheet,
        language=language,
    ) == (text, None)


@pytest.mark.parametrize(
    "text",
    [
        "The benchmark follows the S&P 500.",
        "Reported revenue grew 18% in 2025.",
        "There were thirteen fills.",
        "The return was 99.9%.",
    ],
)
def test_unreferenced_number_does_not_discard_the_draft(fact_sheet, text):
    assert accepted_readout_text(draft(text), facts=fact_sheet, language="en") == (
        text, None
    )


def test_reported_language_mismatch_rejects_the_complete_draft(fact_sheet):
    assert accepted_readout_text(
        draft("An uneven ride.", language="en"), facts=fact_sheet, language="es-419"
    ) == (None, "language_mismatch")


def test_readout_without_figures_is_valid_without_required_mentions(fact_sheet):
    response = draft("An uneven historical ride.")
    assert accepted_readout_text(response, facts=fact_sheet, language="en-US") == (
        response["text"], None
    )


@pytest.mark.parametrize(
    "value", [True, False, float("nan"), float("inf"), -float("inf")]
)
def test_reference_value_must_be_finite_and_not_boolean(fact_sheet, value):
    assert accepted_readout_text(
        draft("Return: 15.1%.", [figure("portfolio.total_return", value)]),
        facts=fact_sheet,
        language="en",
    ) == (None, "invalid_draft")


@pytest.mark.parametrize("unit", ["unknown", "text", "boolean"])
def test_nonnumeric_row_cannot_justify_numeric_reference(fact_sheet, unit):
    fact_sheet["facts"]["portfolio.total_return"]["unit"] = unit
    assert accepted_readout_text(
        draft("Return: 15.1%.", [figure("portfolio.total_return", 15.1)]),
        facts=fact_sheet,
        language="en",
    ) == (None, "invalid_figure_reference")


def test_empty_draft_selects_complete_fallback(fact_sheet):
    assert accepted_readout_text(draft("  "), facts=fact_sheet, language="en") == (
        None, "empty_draft"
    )


def test_punctuation_normalization_preserves_the_whole_draft(fact_sheet):
    assert accepted_readout_text(
        draft("An uneven ride — with a recovery."), facts=fact_sheet, language="en"
    ) == ("An uneven ride, with a recovery.", None)


@pytest.mark.asyncio
@pytest.mark.parametrize("surface", ["quick_take", "breakdown"])
@pytest.mark.parametrize(
    "failure",
    [
        None,
        "language_mismatch",
        "invalid_figure_reference",
        "provider_error",
    ],
)
async def test_composer_one_call_and_complete_fallback_with_precise_reason(
    surface, failure, monkeypatch
):
    from argus.agent_runtime.stages import explain
    from argus.agent_runtime.state.models import RunState
    from argus.api.chat import breakdown
    from argus.domain.research.contracts import ResearchUsage
    from argus.domain.research.perplexity_agent import StructuredAgentResult

    calls = []
    text = "El recorrido histórico fue irregular."
    language = "en" if failure == "language_mismatch" else "es-419"
    response = draft(text, language=language)
    if failure == "invalid_figure_reference":
        response["text"] += " El rendimiento fue 99%."
    if failure == "invalid_figure_reference":
        response["figures"] = [
            {
                "fact_key": "portfolio.total_return",
                "value": 99,
            }
        ]
    result = {
        "metrics": {
            "aggregate": {
                "performance": {
                    "total_return_pct": 15.126,
                    "benchmark_return_pct": 20.421,
                    "delta_vs_benchmark_pct": -5.295,
                }
            }
        },
        "config_snapshot": {"template": "buy_and_hold", "starting_capital": 10000},
        "symbols": ["DOCN"],
        "benchmark_symbol": "SPY",
    }

    def invoke(**kwargs):
        calls.append(kwargs)
        if failure == "provider_error":
            raise RuntimeError("provider unavailable")
        return response

    if surface == "quick_take":

        async def async_invoke(**kwargs):
            return invoke(**kwargs)

        monkeypatch.setattr(explain, "invoke_openrouter_json_schema", async_invoke)
        state = RunState.new(current_user_message="Explain", recent_thread_history=[])
        state.final_response_payload = {"result": result}
        state.confirmation_payload = {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": result["symbols"],
            },
            "optional_parameters": {},
        }
        stage = await explain.explain_stage_async(state=state, language="es-419")
        patch = stage.stage_patch
        rendered = patch["assistant_response"]
        used_fallback = patch["assistant_response_fallback_used"]
        reason = patch.get("assistant_response_failure_mode")
        source = patch["assistant_response_source"]
    else:

        class Client:
            def run_structured(self, prompt, spec, **kwargs):
                return StructuredAgentResult(
                    draft=invoke(prompt=prompt, spec=spec, **kwargs),
                    sources=(),
                    usage=ResearchUsage(model=spec.model),
                    tool_results=(),
                    provider_response_id=None,
                )

        monkeypatch.setattr(
            breakdown,
            "result_breakdown_context",
            lambda run: {**result, "raw_metrics": result["metrics"]},
        )
        message = breakdown.result_breakdown_message_with_metadata(
            object(), language="es-419", client=Client()
        )
        rendered, used_fallback, reason, source = (
            message.text,
            message.fallback_used,
            message.failure_mode,
            message.source,
        )
    assert len(calls) == 1
    assert used_fallback is bool(failure)
    if failure:
        assert text not in rendered
        expected = (
            (
                explain.RESULT_READOUT_FAILURE_LLM_UNAVAILABLE
                if surface == "quick_take"
                else "llm_unavailable_or_contract_rejected"
            )
            if failure == "provider_error"
            else failure
        )
        assert reason == expected
        assert source == "deterministic_fallback"
    else:
        assert rendered == text
        assert reason is None


@pytest.mark.parametrize("language", [None, "", "fr", 123])
def test_breakdown_unsupported_requested_language_never_uses_context_locale(language):
    from argus.api.chat.breakdown import _llm_result_breakdown_with_metadata

    calls = []

    class Client:
        def run_structured(self, *args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("Unsupported language must not call the provider")

    assert _llm_result_breakdown_with_metadata(
        {"language": "en"}, language=language, client=Client()
    ) == (None, "language_mismatch", None, ())
    assert calls == []
