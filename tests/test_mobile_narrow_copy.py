"""Backend-owned narrow-screen copy for the mobile shell.

The backend owns user-facing copy, so a narrow screen gets a shorter Try next
label and a shorter generated title composed here, never clipped in the client.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from argus.agent_runtime.next_experiments import (
    NEXT_EXPERIMENT_ACTION_LABELS,
    NEXT_EXPERIMENT_SHORT_LABELS,
    next_experiment_label_key,
    next_experiment_short_label_key,
    next_experiments_sidecar,
)
from argus.api.naming import (
    NARROW_TITLE_MAX_WORDS,
    WIDE_TITLE_MAX_WORDS,
    constrain_to_word_budget,
    title_word_budget,
)
from argus.api.schemas import ChatStreamRequest

LANGUAGES = ("en", "es-419")
_LABEL_PREFIX = "chat.next_experiments.labels."
_LOCALES = Path(__file__).resolve().parents[1] / "web" / "public" / "locales"


def _kinds() -> set[str]:
    return {
        key.removeprefix(_LABEL_PREFIX)
        for key in NEXT_EXPERIMENT_ACTION_LABELS["en"]
    }


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_row_kind_has_a_short_form(language: str) -> None:
    assert set(NEXT_EXPERIMENT_SHORT_LABELS[language]) == _kinds()


@pytest.mark.parametrize("language", LANGUAGES)
def test_short_form_is_shorter_than_the_full_label(language: str) -> None:
    for kind, short in NEXT_EXPERIMENT_SHORT_LABELS[language].items():
        full = NEXT_EXPERIMENT_ACTION_LABELS[language][
            next_experiment_label_key(kind)
        ]
        assert len(short) < len(full), kind
        assert short.strip() == short


@pytest.mark.parametrize("language", LANGUAGES)
def test_short_form_carries_no_em_dash(language: str) -> None:
    assert not [
        value for value in NEXT_EXPERIMENT_SHORT_LABELS[language].values()
        if "—" in value
    ]


def test_english_and_spanish_short_forms_stay_equivalent() -> None:
    assert set(NEXT_EXPERIMENT_SHORT_LABELS["en"]) == set(
        NEXT_EXPERIMENT_SHORT_LABELS["es-419"]
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_short_labels_are_published_to_the_client_locale(language: str) -> None:
    bundle = json.loads((_LOCALES / language / "common.json").read_text())
    published = bundle["chat"]["next_experiments"]["labels_short"]
    assert published == NEXT_EXPERIMENT_SHORT_LABELS[language]


def test_sidecar_rows_carry_the_short_form() -> None:
    facts = {
        "strategy_family": "buy_and_hold",
        "symbols": ["AAPL"],
        "benchmark_symbol": "SPY",
        "start_date": "2025-08-01",
        "end_date": "2026-08-01",
    }
    sidecar = next_experiments_sidecar(facts)
    if sidecar is None:
        pytest.skip("no experiments offered for this result shape")
    for row in sidecar["rows"]:
        assert row["label_short"] == NEXT_EXPERIMENT_SHORT_LABELS["en"][row["kind"]]
        assert row["label_short_key"] == next_experiment_short_label_key(row["kind"])
        assert len(row["label_short"]) < len(row["label"])


def test_narrow_titles_are_generated_short_not_clipped() -> None:
    assert title_word_budget("narrow") == NARROW_TITLE_MAX_WORDS
    assert title_word_budget("wide") == WIDE_TITLE_MAX_WORDS
    assert title_word_budget(None) == WIDE_TITLE_MAX_WORDS
    assert NARROW_TITLE_MAX_WORDS < WIDE_TITLE_MAX_WORDS


def test_the_budget_is_enforced_rather_than_only_requested() -> None:
    """The prompt asks for a word limit; a model is free to ignore it.

    Without enforcement the overlong title is what gets persisted, and every
    narrow client goes back to clipping it, which is the thing the viewport
    contract exists to avoid.
    """

    overlong = "Apple versus SPY across the last twelve months"
    assert (
        constrain_to_word_budget(overlong, NARROW_TITLE_MAX_WORDS)
        == "Apple versus SPY"
    )
    assert len(constrain_to_word_budget(overlong, WIDE_TITLE_MAX_WORDS).split()) == (
        WIDE_TITLE_MAX_WORDS
    )


def test_a_title_already_inside_the_budget_is_left_alone() -> None:
    for title in ("Apple vs SPY", "Bitcoin", "Weekly Nvidia buys"):
        assert constrain_to_word_budget(title, NARROW_TITLE_MAX_WORDS) == title


def test_trimming_does_not_leave_a_dangling_separator() -> None:
    # A cut mid-phrase reads as damage rather than as a short title.
    assert (
        constrain_to_word_budget("Apple, SPY, and gold over time", 2) == "Apple, SPY"
    )
    assert constrain_to_word_budget("Apple versus - the market", 3) == "Apple versus"


def test_turn_request_carries_an_optional_viewport_band() -> None:
    assert (
        ChatStreamRequest(conversation_id="c1", message="hi").viewport is None
    )
    assert (
        ChatStreamRequest(
            conversation_id="c1", message="hi", viewport="narrow"
        ).viewport
        == "narrow"
    )
    with pytest.raises(ValueError):
        ChatStreamRequest(conversation_id="c1", message="hi", viewport="phone")
