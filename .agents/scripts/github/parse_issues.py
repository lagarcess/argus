#!/usr/bin/env python3
"""
Parse GitHub Issue JSON and format for agent context.

Usage:
    python .agent/scripts/github/parse_issues.py temp/issues/issue_181_raw.json
"""

import json
import sys
from pathlib import Path


def format_issue_for_agent(issue_data: dict) -> str:
    """Format issue data into readable text for agents."""
    number = issue_data.get("number", "Unknown")
    title = issue_data.get("title", "No Title")
    body = issue_data.get("body", "No description provided")
    labels = issue_data.get("labels", [])

    # Extract label names
    label_names = [label.get("name", "") for label in labels if isinstance(label, dict)]

    # Determine issue type from labels
    issue_type = "feature"
    if "bug" in label_names:
        issue_type = "fix"
    elif "chore" in label_names or "documentation" in label_names:
        issue_type = "chore"
    elif "refactor" in label_names:
        issue_type = "refactor"

    output = []
    output.append("=" * 80)
    output.append(f"Issue #{number}: {title}")
    output.append("=" * 80)
    output.append("")
    output.append(body)
    output.append("")
    output.append("=" * 80)
    output.append("IMPLEMENTATION GUIDANCE")
    output.append("=" * 80)
    output.append("")
    output.append("STEP 1: UNDERSTAND THE REQUIREMENT")
    output.append("  - Read the issue description carefully")
    output.append("  - Identify affected files and components")
    output.append("  - Check for related issues or PRs mentioned")
    output.append("")
    output.append("STEP 2: LOCATE THE CODE")
    output.append("  - Use grep/find to locate relevant files")
    output.append("  - Review existing implementation")
    output.append("  - Identify test files (tests/ directory)")
    output.append("")
    output.append("STEP 3: IMPLEMENT THE CHANGES")
    output.append("  - Follow the task checklist if provided")
    output.append("  - Write tests FIRST (TDD approach)")
    output.append("  - Make minimal, focused changes")
    output.append("  - Follow existing code patterns")
    output.append("")
    output.append("STEP 4: VERIFY YOUR CHANGES")
    output.append("  - Run: poetry run pytest tests/ -v")
    output.append("  - Run: poetry run ruff check src")
    output.append("  - Run pre-commit hooks if available")
    output.append("")
    output.append("STEP 5: CREATE PR")
    output.append(f"  - Branch: {issue_type}/issue-{number}-[short-desc]")
    output.append(f"  - Commit: {issue_type}: [concise description] (#{number})")
    output.append("  - Reference this issue in PR description")
    output.append("  - Ensure all CI checks pass")
    output.append("")
    output.append("=" * 80)
    output.append("IMPORTANT REMINDERS")
    output.append("=" * 80)
    output.append("  - DO NOT modify files outside the scope of this issue")
    output.append("  - DO NOT skip writing tests")
    output.append("  - DO keep changes minimal and focused")
    output.append("  - DO follow the existing code style")
    output.append("  - DO check for similar patterns in the codebase")
    output.append("")

    return "\n".join(output)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python .agent/scripts/github/" "parse_issues.py <JSON_FILE>")
        sys.exit(1)

    json_path = Path(sys.argv[1])

    if not json_path.exists():
        print(f"❌ Error: File not found: {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8-sig") as f:
        issue_data = json.load(f)

    formatted_text = format_issue_for_agent(issue_data)

    issue_num = issue_data.get("number", "unknown")
    output_path = json_path.parent / f"issue_{issue_num}.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(formatted_text)

    print(f"✅ Issue formatted and saved to: {output_path}")


if __name__ == "__main__":
    main()
