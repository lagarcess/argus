from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _name(*parts: str) -> str:
    return "".join(parts)


def _module_path(*parts: str) -> str:
    return "_".join(parts)


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_domain_orchestrator_retains_only_non_routing_helpers() -> None:
    source = _source("src/argus/domain/orchestrator.py")

    banned_symbols = [
        _name("classify_chat_turn", "_intent"),
        _name("Chat", "Turn", "Intent"),
        _name("Backtest", "Params", "Update"),
        _name("orchestrate_chat", "_turn"),
        _name("assistant_message_for_chat", "_turn"),
        _name("COMMON", "_NAMES"),
        _name("NON", "_SYMBOLS"),
        _name("_extract_symbols", "_from_text"),
        _name("_extract_deterministic", "_intent"),
        _name("_extract_strategy", "_intent"),
    ]
    for symbol in banned_symbols:
        assert symbol not in source

    assert "def get_starter_prompts" in source
    assert "def suggest_entity_name" in source


def test_api_main_has_no_legacy_orchestrator_wiring() -> None:
    source = _source("src/argus/api/main.py")

    banned_fragments = [
        _name("Backtest", "Conversation", "State"),
        "from argus.domain." + _module_path("backtest", "state", "machine"),
        _name("orchestrate_chat", "_turn"),
        _name("_latest_backtest", "_state"),
        _name("_state_has", "_params"),
        _name("_latest_completed", "_run_id"),
        _name("parse_onboarding", "_goal"),
        "from argus.domain.orchestrator import " + _name("_resolve", "_language"),
    ]
    for fragment in banned_fragments:
        assert fragment not in source


def test_legacy_state_module_is_retired() -> None:
    retired_path = ROOT / "src/argus/domain" / (
        _module_path("backtest", "state", "machine") + ".py"
    )

    assert not retired_path.exists()
