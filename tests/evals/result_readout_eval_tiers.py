"""Read-only proof that a tier experiment changes exactly two mapping values."""

from __future__ import annotations

import ast
import hashlib
import subprocess
from pathlib import Path

TASK_PATH = "src/argus/llm/openrouter_tasks.py"
TIER_MAP = "OPENROUTER_TASK_MODEL_TIERS"


def _normalize(source: bytes, expected: dict[str, str]) -> bytes:
    tree = ast.parse(source)
    mappings = [
        node.value
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == TIER_MAP
    ]
    if len(mappings) != 1 or not isinstance(mappings[0], ast.Dict):
        raise ValueError("one_literal_task_tier_map_required")
    mapping = mappings[0]
    spans = []
    lines = source.splitlines(keepends=True)
    for task, tier in expected.items():
        values = [
            value
            for key, value in zip(mapping.keys, mapping.values, strict=False)
            if isinstance(key, ast.Constant) and key.value == task
        ]
        if (
            len(values) != 1
            or not isinstance(values[0], ast.Constant)
            or values[0].value != tier
        ):
            raise ValueError("unexpected_readout_tier_mapping")
        value = values[0]
        start = sum(map(len, lines[: value.lineno - 1])) + value.col_offset
        end = sum(map(len, lines[: value.end_lineno - 1])) + value.end_col_offset
        spans.append((start, end))
    for start, end in sorted(spans, reverse=True):
        source = source[:start] + b'"READOUT_TIER"' + source[end:]
    return source


def validate_tier_sources(current: bytes, structured: bytes) -> str:
    normalized = _normalize(
        current, {"result_summary": "chat", "result_breakdown": "context"}
    )
    if normalized != _normalize(
        structured, {"result_summary": "structured", "result_breakdown": "structured"}
    ):
        raise ValueError("only_two_readout_tier_values_may_differ")
    return hashlib.sha256(normalized).hexdigest()


def committed_tree(root: Path) -> dict[str, tuple[str, str]]:
    output = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-rz", "HEAD"])
    entries = {}
    for entry in output.split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        entries[path.decode()] = (f"{mode} {kind}", oid)
    return entries


def validate_tier_checkouts(current: Path, structured: Path) -> dict[str, object]:
    """Call after both checkouts were proven clean at their recorded HEADs."""
    trees = [committed_tree(root) for root in (current, structured)]
    changed = {
        path
        for path in trees[0].keys() | trees[1].keys()
        if trees[0].get(path) != trees[1].get(path)
    }
    if changed != {TASK_PATH} or trees[0][TASK_PATH][0] != trees[1][TASK_PATH][0]:
        raise ValueError("only_readout_tier_file_may_differ")
    sources = [
        subprocess.check_output(["git", "-C", str(root), "show", f"HEAD:{TASK_PATH}"])
        for root in (current, structured)
    ]
    signature = validate_tier_sources(*sources)
    return {
        "changed_paths": [TASK_PATH],
        "unchanged_tree_entries": len(trees[0]) - 1,
        "normalized_task_source_sha256": signature,
        "only_changes": {
            "result_summary": ["chat", "structured"],
            "result_breakdown": ["context", "structured"],
        },
    }
