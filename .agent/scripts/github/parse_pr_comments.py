"""
Parse and display GitHub PR comments from JSON dump.

Usage:
    python .agent/scripts/github/parse_pr_comments.py <json_file>
    python .agent/scripts/github/parse_pr_comments.py <json_file> --output <output_dir>
"""

import json
import re
import sys
from pathlib import Path


def parse_pr_comments(
    input_file: Path,
    output_dir: Path | None = None,
) -> None:
    """Parse GitHub API comment JSON and save readable report."""
    if output_dir is None:
        output_dir = Path("temp/pr_comments")

    if not input_file.exists():
        print(f"❌ Error: File not found: {input_file}")
        sys.exit(1)

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            comments = json.load(f)
    except json.JSONDecodeError:
        print(f"❌ Error: Could not parse JSON from {input_file}")
        sys.exit(1)

    if not isinstance(comments, list):
        comments = [comments]

    print(f"🔵 Parsing {len(comments)} comments from " f"{input_file.name}...")

    report_lines: list[str] = []
    report_lines.append(f"PR Comments: {input_file.name}")
    report_lines.append("=" * 80)

    for i, c in enumerate(comments):
        path = c.get("path", "General")
        user = c.get("user", {}).get("login", "Unknown")
        url = c.get("html_url", "N/A")

        # Line range
        end_line = c.get("line") or c.get("original_line") or "N/A"
        start_line = c.get("start_line") or c.get("original_start_line") or end_line
        if start_line == end_line or start_line == "N/A":
            line_str = f"{end_line}"
        else:
            line_str = f"{start_line}-{end_line}"

        # Body cleaning & priority extraction
        raw_body = c.get("body", "")
        priority = "Normal"
        clean_body = raw_body

        prio_match = re.search(
            r"!\[.*?\]\(.*?([a-z]+)-priority\.svg\)",
            raw_body,
            re.IGNORECASE,
        )
        if prio_match:
            prio_slug = prio_match.group(1).lower()
            if "high" in prio_slug:
                priority = "HIGH"
            elif "medium" in prio_slug:
                priority = "MED"
            elif "low" in prio_slug:
                priority = "LOW"
            clean_body = raw_body.replace(prio_match.group(0), "").strip()

        report_lines.append("-" * 80)
        report_lines.append(f"Comment #{i + 1} [{priority}]")
        report_lines.append(f"File:     {path}")
        report_lines.append(f"Lines:    {line_str}")
        report_lines.append(f"User:     {user}")
        report_lines.append(f"URL:      {url}")
        report_lines.append(f"Content:\n{clean_body}\n")

    # Save report
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{input_file.stem}_readable.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print(f"✅ Report saved to: {output_file}")
    print(f"\n📋 Agents: Check {output_file} for full details.")
    print("   Address HIGH priority items immediately.")


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python .agent/scripts/github/"
            "parse_pr_comments.py <json_file> "
            "[--output <output_dir>]"
        )
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_dir = None

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_dir = Path(sys.argv[idx + 1])

    parse_pr_comments(input_file, output_dir)


if __name__ == "__main__":
    main()
