"""Write the enumerated blocks in the message and stream shape record.

The producers own the values. This script is the only writer of the marked
blocks in docs/message-and-stream-shapes.md.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/message-and-stream-shapes.md"
SCHEMAS = ROOT / "src/argus/api/schemas.py"
SRC = ROOT / "src/argus"


def message_fields() -> dict[str, bool]:
    module = ast.parse(SCHEMAS.read_text())
    cls = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "Message"
    )
    fields: dict[str, bool] = {}
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            fields[stmt.target.id] = stmt.value is None
    return fields


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _parse_src() -> list[tuple[Path, ast.AST]]:
    return [
        (path, ast.parse(path.read_text()))
        for path in sorted(SRC.rglob("*.py"))
    ]


def _dict_items(node: ast.Dict, *, strict: bool = False) -> list[tuple[str | None, ast.AST]]:
    items: list[tuple[str | None, ast.AST]] = []
    for key, value in zip(node.keys, node.values, strict=True):
        if key is None:
            items.append((None, value))
            continue
        text = _string_constant(key)
        if text is None:
            if strict:
                raise SystemExit(f"non-string dict key at line {getattr(key, 'lineno', '?')}")
            continue
        items.append((text, value))
    return items


def _literal_keys(node: ast.Dict) -> list[str]:
    keys: list[str] = []
    for key, value in _dict_items(node, strict=True):
        if key is None:
            unpacked = value.body if isinstance(value, ast.IfExp) else value
            if not isinstance(unpacked, ast.Dict):
                raise SystemExit("unpacked payload is not a dict literal")
            keys.extend(_literal_keys(unpacked))
            continue
        keys.append(key)
    return keys


def stage_values() -> list[str]:
    found: set[str] = set()
    for path, tree in _parse_src():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "WorkflowNode":
                for stmt in node.body:
                    if isinstance(stmt, ast.Assign) and stmt.targets:
                        text = _string_constant(stmt.value)
                        if text is None:
                            raise SystemExit(f"WorkflowNode value is not a string in {path}")
                        found.add(text)
            if isinstance(node, ast.Call) and _call_name(node) == "emit_substage":
                if not node.args:
                    raise SystemExit(f"emit_substage without a stage at {path}:{node.lineno}")
                text = _string_constant(node.args[0])
                if text is None:
                    raise SystemExit(
                        f"emit_substage stage is not a string constant at {path}:{node.lineno}"
                    )
                found.add(text)
            if isinstance(node, ast.Dict):
                items = dict(_dict_items(node))
                stage = items.get("stage")
                text = _string_constant(stage) if stage is not None else None
                if text and (items.get("type") is not None or "tool_progress" in items):
                    type_node = items.get("type")
                    if type_node is not None and _string_constant(type_node) not in {
                        None,
                        "stage_start",
                    }:
                        continue
                    found.add(text)
    return sorted(found)


def substages_passing_detail() -> tuple[list[str], list[str]]:
    with_detail: set[str] = set()
    without_detail: set[str] = set()
    for path, tree in _parse_src():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node) != "emit_substage":
                continue
            text = _string_constant(node.args[0]) if node.args else None
            if text is None:
                raise SystemExit(
                    f"emit_substage stage is not a string constant at {path}:{node.lineno}"
                )
            passed = False
            if len(node.args) > 1 and not (
                isinstance(node.args[1], ast.Constant) and node.args[1].value is None
            ):
                passed = True
            for keyword in node.keywords:
                if keyword.arg == "detail" and not (
                    isinstance(keyword.value, ast.Constant) and keyword.value.value is None
                ):
                    passed = True
            (with_detail if passed else without_detail).add(text)
    return sorted(with_detail), sorted(without_detail)


def _literal_strings(node: ast.AST) -> list[str]:
    if not isinstance(node, ast.Subscript):
        raise SystemExit("expected a Literal subscription")
    slice_node = node.slice
    elements = slice_node.elts if isinstance(slice_node, ast.Tuple) else [slice_node]
    values: list[str] = []
    for element in elements:
        text = _string_constant(element)
        if text is None:
            raise SystemExit("Literal member is not a string constant")
        values.append(text)
    return values


def _assigned_literal(path: Path, name: str) -> list[str]:
    tree = ast.parse(path.read_text())
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in stmt.targets
        ):
            return _literal_strings(stmt.value)
    raise SystemExit(f"{name} missing in {path}")


def stage_outcomes() -> list[str]:
    return _assigned_literal(
        ROOT / "src/argus/agent_runtime/stages/interpret_types.py",
        "StageOutcome",
    )


def message_roles() -> list[str]:
    return _assigned_literal(SCHEMAS, "MessageRole")


def tool_progress_fields() -> list[str]:
    path = ROOT / "src/argus/domain/tool_contracts.py"
    tree = ast.parse(path.read_text())
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }

    def fields_of(class_name: str) -> list[str]:
        node = classes[class_name]
        own = [
            stmt.target.id
            for stmt in node.body
            if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
        ]
        inherited: list[str] = []
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in classes:
                inherited.extend(fields_of(base.id))
        return inherited + own

    return fields_of("ToolProgress")


def frame_types() -> list[str]:
    found: set[str] = set()
    for _path, tree in _parse_src():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _call_name(node) == "sse_data":
                if node.args and isinstance(node.args[0], ast.Dict):
                    items = dict(_dict_items(node.args[0]))
                    text = _string_constant(items["type"]) if "type" in items else None
                    if text:
                        found.add(text)
            if isinstance(node, ast.Yield) and isinstance(node.value, ast.Dict):
                items = dict(_dict_items(node.value))
                text = _string_constant(items["type"]) if "type" in items else None
                if text:
                    found.add(text)
            if isinstance(node, ast.FunctionDef) and node.name == "sse_done":
                found.add("done")
    return sorted(found)


def _function(path: Path, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise SystemExit(f"{name} missing in {path}")


def _payload_dict(func: ast.AST) -> ast.Dict:
    for node in ast.walk(func):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in _dict_items(node):
            if key == "payload" and isinstance(value, ast.Dict):
                return value
    raise SystemExit("payload dict missing")


def _projection_dict(func: ast.AST) -> ast.Dict:
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and _call_name(node) == "public_confirmation_projection":
            for arg in node.args:
                if isinstance(arg, ast.Dict):
                    return arg
    raise SystemExit("projection dict missing")


def _assigned_payload_dict(func: ast.AST) -> ast.Dict:
    for node in ast.walk(func):
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "payload"
            and isinstance(node.value, ast.Dict)
        ):
            return node.value
    raise SystemExit("assigned payload missing")


def _returned_dict(func: ast.AST) -> ast.Dict:
    for node in ast.walk(func):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Tuple):
            for element in node.value.elts:
                if isinstance(element, ast.Dict):
                    return element
    raise SystemExit("returned dict missing")


def _subscript_payload_keys(func: ast.AST) -> list[str]:
    keys: list[str] = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Name)
                and target.value.id == "payload"
            ):
                text = _string_constant(target.slice)
                if text is None:
                    raise SystemExit("payload subscript is not a string")
                keys.append(text)
    return keys


def closed_final_keys() -> dict[str, list[str]]:
    agent = ast.parse((ROOT / "src/argus/api/routers/agent.py").read_text())
    retest = ROOT / "src/argus/api/chat/retest.py"
    cancellation = ROOT / "src/argus/api/chat/cancellation.py"
    checkpoint = None
    for node in ast.walk(agent):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in _dict_items(node):
            if key != "payload" or not isinstance(value, ast.Dict):
                continue
            keys = _literal_keys(value)
            if "assistant_response" in keys and "stage_outcome" in keys:
                checkpoint = keys
    if checkpoint is None:
        raise SystemExit("checkpoint final payload missing")
    failure = _function(retest, "failed_retest_turn")
    retry_keys: list[str] = []
    for node in ast.walk(failure):
        if isinstance(node, ast.DictComp):
            iterator = node.generators[0].iter
            if isinstance(iterator, ast.Tuple):
                retry_keys = [
                    text
                    for element in iterator.elts
                    if (text := _string_constant(element)) is not None
                ]
    replay = _payload_dict(_function(cancellation, "replay_events"))
    replay_items = dict(_dict_items(replay, strict=True))
    cancelled = replay_items["confirmation_cancelled"]
    if not isinstance(cancelled, ast.Dict):
        raise SystemExit("confirmation_cancelled is not a dict literal")
    complete = _function(cancellation, "complete_confirmation_cancellation")
    assigned = None
    for node in ast.walk(complete):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Name)
                and target.id == "confirmation_cancelled"
                and isinstance(node.value, ast.Dict)
            ):
                assigned = _literal_keys(node.value)
    if assigned is None:
        raise SystemExit("confirmation_cancelled assignment missing")
    return {
        "checkpoint-final-keys": checkpoint,
        "retest-final-keys": _literal_keys(
            _projection_dict(_function(retest, "complete_retest_turn"))
        ),
        "retest-failure-keys": _literal_keys(_assigned_payload_dict(failure))
        + _subscript_payload_keys(failure),
        "retest-retry-keys": retry_keys,
        "cancel-final-keys": _literal_keys(replay),
        "cancel-complete-keys": _literal_keys(_returned_dict(complete)),
        "cancel-id-keys": _literal_keys(cancelled),
        "cancel-id-assigned-keys": assigned,
    }


def _bullet_block(items: list[str]) -> str:
    return "\n".join(f"- `{item}`" for item in items)


def _message_table(fields: dict[str, bool]) -> str:
    rows = [
        "| Field | Required |",
        "| --- | --- |",
        *[
            f"| `{name}` | {'yes' if required else 'no'} |"
            for name, required in fields.items()
        ],
    ]
    return "\n".join(rows)


def published_blocks() -> dict[str, str]:
    finals = closed_final_keys()
    if finals["cancel-final-keys"] != finals["cancel-complete-keys"]:
        raise SystemExit(
            "cancellation replay and complete_confirmation_cancellation payload keys differ"
        )
    if finals["cancel-id-keys"] != finals["cancel-id-assigned-keys"]:
        raise SystemExit("confirmation_cancelled keys differ between replay and assignment")
    with_detail, without_detail = substages_passing_detail()
    lists = {
        "message-fields": _message_table(message_fields()),
        "message-roles": _bullet_block(message_roles()),
        "frame-types": _bullet_block(frame_types()),
        "stage-values": _bullet_block(stage_values()),
        "substage-detail": _bullet_block(with_detail),
        "substage-no-detail": _bullet_block(without_detail),
        "tool-progress-fields": _bullet_block(tool_progress_fields()),
        "stage-outcomes": _bullet_block(stage_outcomes()),
        "checkpoint-final-keys": _bullet_block(finals["checkpoint-final-keys"]),
        "retest-final-keys": _bullet_block(finals["retest-final-keys"]),
        "retest-failure-keys": _bullet_block(finals["retest-failure-keys"]),
        "retest-retry-keys": _bullet_block(finals["retest-retry-keys"]),
        "cancel-final-keys": _bullet_block(finals["cancel-final-keys"]),
        "cancel-id-keys": _bullet_block(finals["cancel-id-keys"]),
    }
    return lists


def render_document(text: str) -> str:
    for name, body in published_blocks().items():
        start = f"<!-- {name} -->"
        end = f"<!-- /{name} -->"
        if start not in text or end not in text:
            raise SystemExit(f"missing generated block {name} in the shape record")
        before, rest = text.split(start, 1)
        _previous, after = rest.split(end, 1)
        text = f"{before}{start}\n{body}\n{end}\n\n{after.lstrip('\n')}"
    return text


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    DOC.write_text(render_document(DOC.read_text()))


if __name__ == "__main__":
    main()
