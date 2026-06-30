from pathlib import Path

import pytest

from scripts.check_modularity_budget import collect_budgets, format_report


def test_modularity_budget_current_baselines_are_within_threshold() -> None:
    budgets = collect_budgets()

    assert budgets
    assert [budget for budget in budgets if budget.overage > 0] == []


def test_modularity_budget_reports_top_offenders() -> None:
    report = format_report(collect_budgets(), top_count=3)

    assert "Modularity budget report" in report
    assert "src/argus/agent_runtime/llm_interpreter.py" in report
    assert "Budget violations:\n- none" in report


def test_modularity_budget_fails_only_past_allowed_growth(tmp_path: Path) -> None:
    watched_file = tmp_path / "large.py"
    watched_file.write_text("line\n" * 4, encoding="utf-8")
    config = tmp_path / "budget.json"
    config.write_text(
        '{"allowed_growth_lines": 2, "watched_files": {"'
        + str(watched_file)
        + '": 1}}',
        encoding="utf-8",
    )

    [budget] = collect_budgets(config)

    assert budget.baseline_lines == 1
    assert budget.current_lines == 4
    assert budget.limit == 3
    assert budget.overage == 1


def test_modularity_budget_rejects_missing_watched_files(tmp_path: Path) -> None:
    config = tmp_path / "budget.json"
    config.write_text(
        '{"allowed_growth_lines": 2, "watched_files": {"missing.py": 1}}',
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        collect_budgets(config)
