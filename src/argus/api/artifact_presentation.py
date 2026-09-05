"""Reader boundary for immutable artifact prose retained as private context.

Persistence and model inputs keep their original records. Only transport copies
pass here. No language, translation, model call, or historical rewrite belongs
in this boundary.
"""

import json
from collections.abc import Mapping
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, field_serializer

from argus.domain.artifact_presentation_kind import artifact_presentation_kind
from argus.domain.result_figures import result_display_figures, with_result_figures

# These storage fields are private across their historical nesting locations.
# The AST guard forbids a presentation consumer from reading them again.
PRIVATE_ARTIFACT_PROSE_FIELDS = frozenset(
    json.loads(files("argus.domain").joinpath("artifact_prose_fields.json").read_text())
)
ARTIFACT_ROOT_PROSE_FIELDS = frozenset(
    json.loads(
        files("argus.domain").joinpath("artifact_root_prose_fields.json").read_text()
    )
)


def without_private_prose(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: without_private_prose(item)
            for key, item in value.items()
            if key not in PRIVATE_ARTIFACT_PROSE_FIELDS
        }
    if isinstance(value, list):
        return [without_private_prose(item) for item in value]
    return value


def reader_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Strip source prose and materialize old typed artifact intent on read."""
    kind = artifact_presentation_kind(payload)
    public: dict[str, Any] = without_private_prose(payload)
    if kind not in {"result", "breakdown", "assumptions"}:
        return public
    if kind == "result" and not isinstance(public.get("result_fact_bank"), dict):
        # An unavailable lookup is still a terminal result, not an empty turn.
        public["result_fact_bank"] = {}
    for field in ARTIFACT_ROOT_PROSE_FIELDS:
        if field in public:
            public[field] = ""
    intent = public.get("response_intent")
    if kind == "breakdown" and not (
        isinstance(intent, dict) and intent.get("kind") == "result_breakdown"
    ):
        public["response_intent"] = {
            "kind": "result_breakdown",
            "facts": {"result_fact_bank": public.get("result_fact_bank")},
        }
    # Display figures are rounded here, once, from the bank's own metrics; a
    # typed breakdown carries its bank inside the intent, older shapes at root.
    with_result_figures(public.get("result_fact_bank"))
    facts = (public.get("response_intent") or {}).get("facts")
    if isinstance(facts, dict):
        with_result_figures(facts.get("result_fact_bank"))
    return public


def reader_run(value: Any) -> Any:
    """Serialize a public run without changing its private persisted model."""
    if value is None:
        return None
    public = without_private_prose(value.model_dump())
    public["figures"] = result_display_figures(public.get("metrics"))
    return value.model_copy(update=public)


def reader_chat_result(
    payload: Mapping[str, Any], metadata: Mapping[str, Any]
) -> dict[str, Any]:
    from argus.api.chat.confirmation import public_confirmation_projection

    # Live and hydrated replies classify the same persisted action facts.
    return reader_payload(
        public_confirmation_projection(
            {**payload, "chat_action": metadata.get("chat_action")}
        )
    )


class ReaderJobResponse(BaseModel):
    @field_serializer("result_readout", check_fields=False)
    def omit_private_readout(self, _value: str | None) -> None:
        # Older clients retain the slot, but can never receive its stored prose.
        return None


def result_breakdown_metadata(message: Any, run: Any) -> dict[str, Any]:
    """Keep composition provenance beside the typed, reloadable reply facts."""
    from argus.domain.backtest_message_projection import result_fact_bank

    metadata = {
        "response_intent": {
            "kind": "result_breakdown",
            "facts": {
                "result_fact_bank": result_fact_bank(run) if run is not None else None
            },
        },
        "result_breakdown_source": message.source,
        "result_breakdown_fallback_used": message.fallback_used,
    }
    if message.failure_mode is not None:
        metadata["result_breakdown_failure_mode"] = message.failure_mode
    return metadata
