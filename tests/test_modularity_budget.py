from pathlib import Path

import pytest

from scripts.check_modularity_budget import (
    SourceFileSize,
    collect_budgets,
    collect_source_sizes,
    format_report,
)


def test_modularity_budget_current_baselines_are_within_threshold() -> None:
    budgets = collect_budgets()

    assert budgets
    assert [budget for budget in budgets if budget.overage > 0] == []


def test_modularity_budget_reports_scanned_top_offenders_and_watched_status() -> None:
    budgets = collect_budgets()
    report = format_report(
        budgets,
        top_count=2,
        source_sizes=[
            SourceFileSize(Path("web/components/new-large-file.tsx"), 9999),
            SourceFileSize(Path("src/argus/agent_runtime/llm_interpreter.py"), 5279),
        ],
    )

    assert "Top production files by current line count" in report
    assert "web/components/new-large-file.tsx: 9999 lines" in report
    assert "src/argus/agent_runtime/llm_interpreter.py: 5279 lines (watched)" in report
    assert "Watched-file budget status" in report
    assert "Budget violations:\n- none" in report


def test_modularity_budget_scans_production_sources_without_surprise_failures(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    test_root = tmp_path / "web" / "__tests__"
    source_root.mkdir()
    test_root.mkdir(parents=True)
    production_file = source_root / "large.py"
    excluded_test_file = test_root / "large.test.ts"
    production_file.write_text("line\n" * 4, encoding="utf-8")
    excluded_test_file.write_text("line\n" * 99, encoding="utf-8")
    config = tmp_path / ".agent" / "modularity_budget.json"
    config.parent.mkdir()
    config.write_text(
        """
        {
          "scan_roots": ["src", "web"],
          "scan_extensions": [".py", ".ts"],
          "scan_exclude_globs": ["web/__tests__/**"],
          "watched_files": {}
        }
        """,
        encoding="utf-8",
    )

    sizes = collect_source_sizes(config)

    assert sizes == [SourceFileSize(Path("src/large.py"), 4)]


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


def test_modularity_budget_resolves_repo_relative_paths_from_config_location(
    tmp_path: Path,
) -> None:
    watched_file = tmp_path / "src" / "large.py"
    watched_file.parent.mkdir()
    watched_file.write_text("line\n" * 2, encoding="utf-8")
    config = tmp_path / ".agent" / "modularity_budget.json"
    config.parent.mkdir()
    config.write_text(
        '{"allowed_growth_lines": 2, "watched_files": {"src/large.py": 2}}',
        encoding="utf-8",
    )

    [budget] = collect_budgets(config)

    assert budget.path == Path("src/large.py")
    assert budget.current_lines == 2
    assert budget.overage == 0


def test_modularity_budget_rejects_missing_watched_files(tmp_path: Path) -> None:
    config = tmp_path / "budget.json"
    config.write_text(
        '{"allowed_growth_lines": 2, "watched_files": {"missing.py": 1}}',
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        collect_budgets(config)
