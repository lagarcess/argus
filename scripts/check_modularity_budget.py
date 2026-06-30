#!/usr/bin/env python3
"""Guard large-file modularity budgets without forcing immediate refactors.

The guard compares watched files against recorded line-count baselines and fails
only when a watched file grows beyond the shared allowed-growth threshold.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path(".agent/modularity_budget.json")


@dataclass(frozen=True)
class FileBudget:
    path: Path
    baseline_lines: int
    current_lines: int
    allowed_growth_lines: int

    @property
    def limit(self) -> int:
        return self.baseline_lines + self.allowed_growth_lines

    @property
    def growth(self) -> int:
        return self.current_lines - self.baseline_lines

    @property
    def overage(self) -> int:
        return max(0, self.current_lines - self.limit)


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config.get("watched_files"), dict):
        raise ValueError("modularity budget config requires a watched_files object")
    return config


def collect_budgets(config_path: Path = DEFAULT_CONFIG) -> list[FileBudget]:
    config = _load_config(config_path)
    allowed_growth_lines = int(config.get("allowed_growth_lines", 75))
    budgets: list[FileBudget] = []
    for raw_path, raw_baseline in sorted(config["watched_files"].items()):
        file_path = Path(raw_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Watched modularity file is missing: {raw_path}")
        budgets.append(
            FileBudget(
                path=file_path,
                baseline_lines=int(raw_baseline),
                current_lines=_line_count(file_path),
                allowed_growth_lines=allowed_growth_lines,
            )
        )
    return budgets


def format_report(budgets: list[FileBudget], top_count: int) -> str:
    offenders = sorted(budgets, key=lambda item: item.current_lines, reverse=True)
    lines = [
        "Modularity budget report",
        "========================",
        "",
        "Top watched large files by current line count:",
    ]
    for budget in offenders[:top_count]:
        lines.append(
            f"- {budget.path}: {budget.current_lines} lines "
            f"(baseline {budget.baseline_lines}, growth {budget.growth:+}, "
            f"limit {budget.limit})"
        )
    violations = [budget for budget in offenders if budget.overage > 0]
    lines.extend(["", "Budget violations:"])
    if not violations:
        lines.append("- none")
    else:
        for budget in violations:
            lines.append(f"- {budget.path}: {budget.overage} lines over limit {budget.limit}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check large-file modularity budgets.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--top", type=int, default=None)
    args = parser.parse_args()

    config = _load_config(args.config)
    top_count = args.top or int(config.get("top_offender_count", 10))
    budgets = collect_budgets(args.config)
    print(format_report(budgets, top_count))
    return 1 if any(budget.overage > 0 for budget in budgets) else 0


if __name__ == "__main__":
    raise SystemExit(main())
