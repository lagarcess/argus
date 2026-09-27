from __future__ import annotations

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/message-and-stream-shapes.md"
SCHEMAS = ROOT / "src/argus/api/schemas.py"
OPENAPI = ROOT / "docs/api/openapi.yaml"
PARSER = ROOT / "web/lib/argus-api.ts"
UI_MESSAGE = ROOT / "web/components/chat/types.ts"
HYDRATION = ROOT / "web/lib/chat-message-hydration.ts"
SRC = ROOT / "src/argus"


def _section(text: str, heading: str) -> str:
    return text.split(heading, 1)[1].split("\n## ", 1)[0]


def _table_rows(section: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in section.splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        rows[cells[0].strip("`")] = cells[1]
    return rows


def _message_fields() -> dict[str, bool]:
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


def _message_roles() -> list[str]:
    module = ast.parse(SCHEMAS.read_text())
    for stmt in module.body:
        if not isinstance(stmt, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "MessageRole" for target in stmt.targets):
            continue
        value = stmt.value
        assert isinstance(value, ast.Subscript)
        roles = value.slice
        assert isinstance(roles, ast.Tuple)
        return [elt.value for elt in roles.elts if isinstance(elt, ast.Constant)]
    raise AssertionError("MessageRole missing")


def _openapi_message() -> dict:
    document = yaml.safe_load(OPENAPI.read_text())
    return document["components"]["schemas"]["Message"]


def test_saved_message_fields_match_schema_and_openapi() -> None:
    published = _table_rows(_section(DOC.read_text(), "## Saved message fields"))
    fields = _message_fields()
    assert published == {
        name: "yes" if required else "no" for name, required in fields.items()
    }
    schema = _openapi_message()
    assert list(schema["properties"]) == list(fields)
    assert schema["required"] == [name for name, required in fields.items() if required]
    assert schema["properties"]["role"]["enum"] == _message_roles()
    assert schema["properties"]["metadata"]["anyOf"][0]["additionalProperties"] is True


def test_published_stream_frames_match_emitters() -> None:
    doc = DOC.read_text()
    assert "The emitters do not send a frame whose `type` is `title`." in doc
    sources = "\n".join(path.read_text() for path in SRC.rglob("*.py"))
    assert '"type": "title"' not in sources
    for frame_type in ("stage_start", "token", "stage_outcome", "final", "error"):
        assert f'"type": "{frame_type}"' in sources
        assert f"### `{frame_type}`" in doc
    assert "data: [DONE]" in (ROOT / "src/argus/api/chat/streaming.py").read_text()
    assert "### `done`" in doc


def test_parser_and_ui_mappings_match_clients() -> None:
    doc = DOC.read_text()
    parser = PARSER.read_text()
    assert 'text: String(payload.content ?? payload.text ?? "")' in parser
    assert "payload.message ?? payload.detail" in parser
    assert "payload.payload ?? {}" in parser
    assert "`text` from `content`" in doc
    assert "`detail` from `message`" in doc
    assert 'role: "user" | "ai"' in UI_MESSAGE.read_text()
    assert 'role: message.role === "user" ? "user" : "ai"' in HYDRATION.read_text()
    assert "Every other wire role becomes `ai`." in doc
    api_message = parser.split("export type ApiMessage = {", 1)[1].split("};", 1)[0]
    for field in _message_fields():
        assert field in api_message
