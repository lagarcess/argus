from __future__ import annotations

from pathlib import Path

import yaml

from scripts.publish_message_stream_shapes import message_fields, message_roles

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/message-and-stream-shapes.md"
OPENAPI = ROOT / "docs/api/openapi.yaml"
PARSER = ROOT / "web/lib/argus-api.ts"
UI_MESSAGE = ROOT / "web/components/chat/types.ts"
HYDRATION = ROOT / "web/lib/chat-message-hydration.ts"
SRC = ROOT / "src/argus"


def _openapi_message() -> dict:
    document = yaml.safe_load(OPENAPI.read_text())
    return document["components"]["schemas"]["Message"]


def test_openapi_message_matches_schema() -> None:
    fields = message_fields()
    schema = _openapi_message()
    assert list(schema["properties"]) == list(fields)
    assert schema["required"] == [name for name, required in fields.items() if required]
    assert schema["properties"]["role"]["enum"] == message_roles()
    assert schema["properties"]["metadata"]["anyOf"][0]["additionalProperties"] is True


def test_no_emitter_sends_a_title_frame() -> None:
    doc = DOC.read_text()
    assert "The emitters do not send a frame whose `type` is `title`." in doc
    sources = "\n".join(path.read_text() for path in SRC.rglob("*.py"))
    assert '"type": "title"' not in sources


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
    for field in message_fields():
        assert field in api_message
