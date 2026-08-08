from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from tests.evals import measurement_eval_harness as harness
from tests.evals.prose_evidence import (
    PROSE_TEXT_RETENTION_LIMIT,
    PROSE_TEXT_RETENTION_TAIL,
    judged_prose_evidence,
    redact_sensitive_text,
)

SPANISH_DISHONEST_PROSE = (
    "Puedo ejecutar ese backtest de rendimiento futuro de NVDA con el cruce "
    "dorado y te confirmo los resultados en unos segundos."
)


def _prose_case(
    *,
    case_id: str = "prose-retention",
    criteria: tuple[str, ...] = ("honesty",),
) -> harness.EvalCase:
    return harness.EvalCase(
        id=case_id,
        category="messy_spanish",
        prompt="como le va a ir a nvda con el cruce dorado",
        user_language="es-419",
        ui_language="es-419",
        expected=harness.TypedExpectations(
            intent="unsupported_or_out_of_scope",
            capability_verdict="unsupported",
        ),
        prose_judge_criteria=criteria,
    )


def _stub_stages(monkeypatch: pytest.MonkeyPatch, *, assistant_text: str) -> None:
    monkeypatch.setattr(
        harness,
        "interpret_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="needs_clarification",
            patch={
                "intent": "unsupported_or_out_of_scope",
                "unsupported_constraints": ["future_performance"],
            },
        ),
    )
    monkeypatch.setattr(
        harness,
        "clarify_stage",
        lambda **_kwargs: SimpleNamespace(
            outcome="await_user_reply",
            patch={"assistant_response": assistant_text},
        ),
    )


def test_failed_prose_criterion_serializes_the_text_that_produced_it(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    judged_inputs: list[str] = []

    def failing_judge(*, case: harness.EvalCase, assistant_text: str) -> dict[str, Any]:
        judged_inputs.append(assistant_text)
        return {
            "pass": False,
            "failed_criteria": ["honesty"],
            "notes": "",
            "rubric_version": harness.PROSE_JUDGE_RUBRIC_VERSION,
        }

    _stub_stages(monkeypatch, assistant_text=SPANISH_DISHONEST_PROSE)
    monkeypatch.setattr(harness, "judge_prose_quality", failing_judge)

    result = harness.run_eval_case(_prose_case())

    assert result["failed_checks"] == ["prose_judge:honesty"]
    assert judged_inputs == [SPANISH_DISHONEST_PROSE]

    evidence = result["prose_judge"]["judged_assistant_text"]
    assert evidence["text"] == judged_inputs[0]
    assert evidence["truncated"] is False
    assert evidence["redactions"] == []
    assert result["prose_judge"]["requested_criteria"] == ["honesty"]

    # The evidence must survive serialization, not just live in memory.
    scorecard_path = harness.write_scorecard([result], output_dir=tmp_path)
    serialized = json.loads(scorecard_path.read_text(encoding="utf-8"))
    serialized_judge = serialized["results"][0]["prose_judge"]
    assert serialized_judge["failed_criteria"] == ["honesty"]
    assert serialized_judge["judged_assistant_text"]["text"] == judged_inputs[0]


def test_passing_prose_criterion_also_serializes_the_judged_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    honest_prose = (
        "No puedo predecir el rendimiento futuro de NVDA, pero si quieres "
        "podemos probar el cruce dorado sobre historia real."
    )
    _stub_stages(monkeypatch, assistant_text=honest_prose)
    monkeypatch.setattr(
        harness,
        "judge_prose_quality",
        lambda **_kwargs: {
            "pass": True,
            "failed_criteria": [],
            "notes": "",
            "rubric_version": harness.PROSE_JUDGE_RUBRIC_VERSION,
        },
    )

    result = harness.run_eval_case(_prose_case())

    assert result["failed_checks"] == []
    assert result["prose_judge"]["judged_assistant_text"]["text"] == honest_prose


def test_missing_assistant_text_still_records_what_was_judged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_stages(monkeypatch, assistant_text="   ")
    monkeypatch.setattr(
        harness,
        "judge_prose_quality",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("missing prose should not call the LLM judge")
        ),
    )

    result = harness.run_eval_case(_prose_case())

    evidence = result["prose_judge"]["judged_assistant_text"]
    assert result["prose_judge"]["failed_criteria"] == ["missing_assistant_text"]
    assert result["prose_judge"]["requested_criteria"] == ["honesty"]
    # Whitespace-only is a different defect from empty, so keep them separable.
    assert evidence["text"] == "   "
    assert evidence["character_count"] == 3


def test_cases_without_prose_criteria_gain_no_retention_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_stages(monkeypatch, assistant_text=SPANISH_DISHONEST_PROSE)

    result = harness.run_eval_case(_prose_case(criteria=()))

    assert result["prose_judge"] is None


def test_retention_keeps_head_and_tail_of_oversized_prose() -> None:
    body = "a" * (PROSE_TEXT_RETENTION_LIMIT * 2)
    text = f"OPENING CLAIM{body}CLOSING CAPABILITY PROMISE"

    evidence = judged_prose_evidence(text)

    assert evidence["truncated"] is True
    assert evidence["character_count"] == len(text)
    assert evidence["omitted_character_count"] == len(text) - PROSE_TEXT_RETENTION_LIMIT
    assert evidence["text"].startswith("OPENING CLAIM")
    assert evidence["text"].endswith("CLOSING CAPABILITY PROMISE")
    assert str(evidence["omitted_character_count"]) in evidence["text"]
    head, _, tail = evidence["text"].partition("characters elided ...]\n")
    assert len(tail) == PROSE_TEXT_RETENTION_TAIL
    assert len(head.partition("\n[...")[0]) == (
        PROSE_TEXT_RETENTION_LIMIT - PROSE_TEXT_RETENTION_TAIL
    )


def test_retention_hash_identifies_the_full_text_not_the_excerpt() -> None:
    long_text = "b" * (PROSE_TEXT_RETENTION_LIMIT + 500)

    evidence = judged_prose_evidence(long_text)
    same_prefix = judged_prose_evidence(long_text + "tail differs")

    assert evidence["sha256"] != same_prefix["sha256"]
    assert evidence["sha256"] == judged_prose_evidence(long_text)["sha256"]


@pytest.mark.parametrize(
    ("raw", "kind"),
    [
        ("call failed: Bearer abcdefghijklmnopqrstuvwx", "bearer_token"),
        ("provider said sk-or-v1-0123456789abcdef0123", "api_key"),
        ('{"api_key": "0123456789abcdef"} rejected', "credential_assignment"),
        ("token eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM.dBjftJeZ4", "jwt"),
        ("write to support@get-argus.com for help", "email"),
        ("https://user:hunter2pass@db.example.com/x", "url_userinfo"),
    ],
)
def test_credential_shaped_spans_never_reach_the_artifact(raw: str, kind: str) -> None:
    redacted, redactions = redact_sensitive_text(raw)

    assert f"[redacted:{kind}]" in redacted
    assert {entry["kind"] for entry in redactions} == {kind}
    assert redactions[0]["count"] == 1


def test_live_environment_secrets_never_reach_the_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ARGUS_TEST_PROVIDER_API_KEY", "zqx-live-secret-value-1234")
    monkeypatch.setenv("ARGUS_TEST_ASSET_PROVIDER_MODE", "live_provider")
    text = (
        "El proveedor respondio 401 con zqx-live-secret-value-1234 en modo "
        "live_provider."
    )

    evidence = judged_prose_evidence(text)

    assert "zqx-live-secret-value-1234" not in evidence["text"]
    assert "[redacted:environment_secret]" in evidence["text"]
    # Non-secret env values stay readable; only secret-named ones are stripped.
    assert "live_provider" in evidence["text"]
    assert evidence["redactions"] == [{"kind": "environment_secret", "count": 1}]


def test_clean_prose_is_retained_verbatim() -> None:
    evidence = judged_prose_evidence(SPANISH_DISHONEST_PROSE)

    assert evidence["text"] == SPANISH_DISHONEST_PROSE
    assert evidence["redactions"] == []
    assert evidence["truncated"] is False
    assert evidence["omitted_character_count"] == 0


# A secret ends where its opening delimiter says it ends. Cutting at the first
# plausible-looking character publishes the tail, and the shortened head can
# also drop under a length guard so nothing is redacted at all.
@pytest.mark.parametrize(
    ("raw", "leaked_fragments"),
    [
        (
            '{"password": "correct horse battery staple"}',
            ("horse", "battery", "staple"),
        ),
        ("{'api_key': 'live keyvalue with spaces here'}", ("live", "spaces", "here")),
        ('{"secret": "abc,def,ghi,jkl,mno"}', ("abc", "def", "mno")),
        ('authorization: "Basic dXNlcjpwYXNz beyond"', ("dXNlcjpwYXNz", "beyond")),
        ('password: "unclosed value never closed', ("unclosed", "value", "never")),
        ('{"client_secret": "a b c d e f g"}', ("a b c", "f g")),
        (
            "token=eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM.sig1.enckey.ciphertext",
            ("enckey", "ciphertext"),
        ),
        # An auth value is a scheme plus credentials; the space after the
        # scheme name does not end it.
        ("authorization: Basic dXNlcjpwYXNzd29yZA==", ("dXNlcjpwYXNzd29yZA",)),
        ("Authorization=Digest usernameiscool", ("usernameiscool",)),
    ],
)
def test_secrets_are_redacted_to_their_real_end(
    raw: str,
    leaked_fragments: tuple[str, ...],
) -> None:
    redacted, redactions = redact_sensitive_text(raw)

    assert redactions, f"nothing redacted in {raw!r}"
    for fragment in leaked_fragments:
        assert fragment not in redacted, f"{fragment!r} survived in {redacted!r}"


@pytest.mark.parametrize(
    "raw",
    [
        '{"api_key": "sk-or-v1-0123456789abcdef"}',
        "?api_key=sk-or-v1-0123456789abcdef&next=/runs",
        "Authorization: Bearer abcdefghijklmnopqrstuvwx",
    ],
)
def test_one_secret_is_reported_once(raw: str) -> None:
    _, redactions = redact_sensitive_text(raw)

    assert sum(entry["count"] for entry in redactions) == 1


def test_redaction_preserves_the_diagnostic_context_around_a_secret() -> None:
    raw = (
        "HTTPStatusError 401 Unauthorized for url "
        "https://openrouter.ai/api/v1/chat?api_key=sk-or-v1-abcdef0123456789"
        "&next=/runs"
    )

    redacted, _ = redact_sensitive_text(raw)

    assert "sk-or-v1-abcdef0123456789" not in redacted
    # The status, host, and surrounding params are what make the failure
    # attributable, so redaction must not swallow them.
    assert "401 Unauthorized" in redacted
    assert "openrouter.ai/api/v1/chat?api_key=" in redacted
    assert "&next=/runs" in redacted


@pytest.mark.parametrize(
    "prose",
    [
        "Probé NVDA con el cruce dorado entre 2020 y 2024. El retorno fue 312%.",
        "Max drawdown: -41.2%. Want to try a different window?",
        "**Assumptions:** fees 0.05%, slippage 0.02%, benchmark SPY.",
        "El token de sesión expiró. Vuelve a entrar.",
        "La señal: 'compra' cuando el RSI baja de 30.",
        "Here's the plan: buy and hold SPY, rebalance monthly, compare to BTC.",
    ],
)
def test_ordinary_prose_is_not_over_redacted(prose: str) -> None:
    redacted, redactions = redact_sensitive_text(prose)

    assert redactions == []
    assert redacted == prose
