"""Add one authored eligible turn after the four-turn fixture was published."""

import json
import runpy
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PRIVATE = ROOT / "temp/share-answer-qa"
runpy.run_path(str(Path(__file__).with_name("start-api.py")))

from argus.domain.supabase_gateway import SupabaseGateway  # noqa: E402

path = PRIVATE / "selection-fixture.json"
record = json.loads(path.read_text())
assert "research_4" not in record["messages"], "Reuse the existing fifth turn."
owner = json.loads((PRIVATE / "owner.json").read_text())
gateway = SupabaseGateway.from_env()
messages = gateway.list_messages(
    user_id=owner["owner_id"], conversation_id=record["conversation_id"], limit=None
)
source = next(m for m in messages if m.id == record["messages"]["research_3"])
common = {"user_id": owner["owner_id"], "conversation_id": record["conversation_id"]}
gateway.create_message(
    **common,
    role="user",
    content="Authored fifth eligible example: selection must respect the four-answer cap.",
)
message = gateway.create_message(
    **common,
    role="assistant",
    content="This authored fifth example checks the four-answer selection cap. It makes no market claim.",
    metadata=deepcopy(source.metadata),
)
record["messages"]["research_4"] = message.id
path.write_text(json.dumps(record, indent=2))
print(json.dumps({"eligible_turns": 5, "new_provider_calls": 0}))
