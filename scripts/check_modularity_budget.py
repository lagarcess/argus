#!/usr/bin/env python3
"""Guard large-file modularity budgets without forcing immediate refactors.

The guard compares explicitly watched files against recorded line-count baselines
and fails only when a watched file grows beyond the shared allowed-growth
threshold. It also scans production source roots for a non-blocking top-offender
report so newly large files are visible without becoming surprise CI failures.
"""

from __future__ import annotations

import argparse
import fnmatch
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


@dataclass(frozen=True)
class SourceFileSize:
    path: Path
    lines: int


def _line_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def _load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    if not isinstance(config.get("watched_files"), dict):
        raise ValueError("modularity budget config requires a watched_files object")
    return config


def _repo_root(config_path: Path) -> Path:
    resolved = config_path.resolve()
    if resolved.parts[-2:] == (".agent", "modularity_budget.json"):
        return resolved.parents[1]
    return Path.cwd().resolve()


def _display_path(path: Path, root: Path) -> Path:
    try:
        return path.resolve().relative_to(root)
    except ValueError:
        return path


def _candidate_paths(config: dict[str, Any], root: Path) -> list[Path]:
    extensions = tuple(str(item) for item in config.get("scan_extensions", []))
    exclude_globs = [str(item) for item in config.get("scan_exclude_globs", [])]
    candidates: list[Path] = []
    for raw_root in config.get("scan_roots", []):
        scan_root = root / str(raw_root)
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*"):
            if not path.is_file() or not path.name.endswith(extensions):
                continue
            relative = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(relative, pattern) for pattern in exclude_globs):
                continue
            candidates.append(path)
    return sorted(candidates)


def collect_source_sizes(config_path: Path = DEFAULT_CONFIG) -> list[SourceFileSize]:
    config = _load_config(config_path)
    root = _repo_root(config_path)
    return [
        SourceFileSize(path=_display_path(path, root), lines=_line_count(path))
        for path in _candidate_paths(config, root)
    ]


def collect_budgets(config_path: Path = DEFAULT_CONFIG) -> list[FileBudget]:
    config = _load_config(config_path)
    root = _repo_root(config_path)
    allowed_growth_lines = int(config.get("allowed_growth_lines", 75))
    budgets: list[FileBudget] = []
    for raw_path, raw_baseline in sorted(config["watched_files"].items()):
        file_path = Path(raw_path)
        resolved_path = file_path if file_path.is_absolute() else root / file_path
        if not resolved_path.exists():
            raise FileNotFoundError(f"Watched modularity file is missing: {raw_path}")
        budgets.append(
            FileBudget(
                path=_display_path(resolved_path, root),
                baseline_lines=int(raw_baseline),
                current_lines=_line_count(resolved_path),
                allowed_growth_lines=allowed_growth_lines,
            )
        )
    return budgets


def format_report(
    budgets: list[FileBudget],
    top_count: int,
    source_sizes: list[SourceFileSize] | None = None,
) -> str:
    watched_by_size = sorted(budgets, key=lambda item: item.current_lines, reverse=True)
    scanned_by_size = sorted(
        source_sizes or [
            SourceFileSize(path=budget.path, lines=budget.current_lines)
            for budget in budgets
        ],
        key=lambda item: item.lines,
        reverse=True,
    )
    lines = [
        "Modularity budget report",
        "========================",
        "",
        "Top production files by current line count:",
    ]
    for source_file in scanned_by_size[:top_count]:
        watched_marker = " (watched)" if any(
            budget.path == source_file.path for budget in budgets
        ) else ""
        lines.append(f"- {source_file.path}: {source_file.lines} lines{watched_marker}")

    lines.extend(["", "Watched-file budget status:"])
    for budget in watched_by_size[:top_count]:
        lines.append(
            f"- {budget.path}: {budget.current_lines} lines "
            f"(baseline {budget.baseline_lines}, growth {budget.growth:+}, "
            f"limit {budget.limit})"
        )

    violations = [budget for budget in watched_by_size if budget.overage > 0]
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
    source_sizes = collect_source_sizes(args.config)
    print(format_report(budgets, top_count, source_sizes))
    return 1 if any(budget.overage > 0 for budget in budgets) else 0


if __name__ == "__main__":
    raise SystemExit(main())
