from __future__ import annotations

import ast
from pathlib import Path

RUNTIME_INTENT_FILES = [
    "src/argus/agent_runtime/stages/interpret.py",
    "src/argus/agent_runtime/llm_interpreter.py",
    "src/argus/agent_runtime/semantic_integrity.py",
    "src/argus/agent_runtime/strategy_contract.py",
    "src/argus/agent_runtime/stages/execute.py",
    "src/argus/agent_runtime/rule_specs.py",
]


def test_runtime_intent_boundary_does_not_depend_on_regex_nlu() -> None:
    """Strategy/runtime semantics must come from typed interpretation, not regex gates."""
    violations: list[str] = []

    for relative_path in RUNTIME_INTENT_FILES:
        path = Path(relative_path)
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                violations.extend(
                    f"{relative_path}: import {alias.name}"
                    for alias in node.names
                    if alias.name == "re"
                )
            if isinstance(node, ast.ImportFrom) and node.module == "re":
                violations.append(f"{relative_path}: from re import ...")
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "re"
            ):
                violations.append(f"{relative_path}: re.{node.attr}")

    assert violations == []


def test_runtime_does_not_restore_raw_message_semantic_routers() -> None:
    """Runtime routing must trust structured interpreter fields, not prose scanners."""
    forbidden_by_file = {
        "src/argus/agent_runtime/stages/interpret.py": [
            "_latest_result_followup_semantically_indicated",
            "_is_affirmative_pending_resolution_reply",
            "_typed_pending_need_fallback_stage_result_if_applicable",
            "typed_pending_need_validator_used",
            "summary = str(decision.user_goal_summary or \"\").lower()",
        ],
        "src/argus/agent_runtime/semantic_integrity.py": [
            "_current_turn_has_signal_rule_reference",
            "_semantic_tokens",
        ],
        "src/argus/agent_runtime/strategy_contract.py": [
            "_date_range_from_raw_phrase",
            "_extract_period_label_from_raw_phrase",
        ],
        "src/argus/agent_runtime/rule_specs.py": [
            "moving_average_crossover_rules_from_text",
            "_rule_tokens",
            "_moving_average_mentions",
        ],
        "src/argus/agent_runtime/llm_interpreter.py": [
            "Nvidia to NVDA",
            "Apple to AAPL",
            "Tesla to TSLA",
            "Microsoft to MSFT",
            "_message_looks_like_investing_experiment",
            "_message_asks_for_capability_inventory",
        ],
        "src/argus/agent_runtime/stages/confirm.py": [
            "Ready to test",
            "Use the card to run it when you are ready",
            "entry rule:",
        ],
    }
    violations: list[str] = []

    for relative_path, tokens in forbidden_by_file.items():
        source = Path(relative_path).read_text()
        for token in tokens:
            if token in source:
                violations.append(f"{relative_path}: {token}")

    assert violations == []


def test_runtime_contracts_do_not_own_human_language_date_tables() -> None:
    """Date language belongs behind argus.nlp.natural_time, not runtime contracts."""

    forbidden_by_file = {
        "src/argus/agent_runtime/strategy_contract.py": [
            "MONTH_ALIASES",
            "_month_year_span",
            "_month_span_with_shared_year",
            "_build_month_year_date",
        ],
        "src/argus/agent_runtime/run_field_contract.py": [
            "MONTH_ALIASES",
            "MONTH_TOKENS",
            "_month_year_date_range_from_tokens",
            "_month_year_endpoint",
        ],
    }
    violations: list[str] = []

    for relative_path, tokens in forbidden_by_file.items():
        source = Path(relative_path).read_text()
        for token in tokens:
            if token in source:
                violations.append(f"{relative_path}: {token}")

    assert violations == []
