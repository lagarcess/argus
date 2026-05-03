from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

ToneName = Literal["friendly", "concise"]
VerbosityName = Literal["low", "medium", "high"]
ExpertiseMode = Literal["beginner", "intermediate", "advanced"]
MessageRole = Literal["user", "assistant", "system", "tool"]
FieldExtractionStatus = Literal["resolved", "missing", "ambiguous", "unsupported"]

IntentName = Literal[
    "beginner_guidance",
    "strategy_drafting",
    "backtest_execution",
    "results_explanation",
    "collection_management",
    "conversation_followup",
    "unsupported_or_out_of_scope",
]

TaskRelation = Literal["new_task", "continue", "refine", "ambiguous"]


def freeze_state_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: freeze_state_payload(nested_value) for key, nested_value in value.items()}
        )
    if isinstance(value, list):
        return tuple(freeze_state_payload(item) for item in value)
    if isinstance(value, tuple):
        return tuple(freeze_state_payload(item) for item in value)
    if isinstance(value, set):
        return frozenset(freeze_state_payload(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(freeze_state_payload(item) for item in value)
    return value


class ConversationMessage(BaseModel):
    role: MessageRole
    content: str


class StrategySummary(BaseModel):
    strategy_thesis: str | None = None
    asset_universe: list[str] = Field(default_factory=list)
    entry_logic: str | None = None
    exit_logic: str | None = None
    date_range: str | None = None
    extra_parameters: dict[str, Any] = Field(default_factory=dict)


class ExtractedFieldValue(BaseModel):
    raw_value: str | None = None
    normalized_value: Any | None = None
    status: FieldExtractionStatus


class AmbiguousField(BaseModel):
    field_name: str
    raw_value: str
    candidate_normalized_value: Any | None = None
    reason_code: str


class SimplificationOption(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    replacement_values: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def freeze_replacement_values(self) -> "SimplificationOption":
        object.__setattr__(
            self,
            "replacement_values",
            MappingProxyType(
                {
                    key: freeze_state_payload(value)
                    for key, value in self.replacement_values.items()
                }
            ),
        )
        return self

    @field_serializer("replacement_values")
    def serialize_replacement_values(self, value: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(nested_value)
            for key, nested_value in value.items()
        }


class UnsupportedConstraint(BaseModel):
    category: str
    raw_value: str
    explanation: str
    simplification_options: list[SimplificationOption] = Field(default_factory=list)


class ArtifactReference(BaseModel):
    artifact_kind: str
    artifact_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskSnapshot(BaseModel):
    latest_task_type: IntentName | None = None
    completed: bool | None = None
    confirmed_strategy_summary: StrategySummary | None = None
    latest_backtest_result_reference: ArtifactReference | None = None
    latest_collection_action_reference: ArtifactReference | None = None
    last_unresolved_follow_up: str | None = None


class ConfirmationPayload(BaseModel):
    strategy: StrategySummary
    optional_parameters: dict[str, Any] = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
    tool_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    outcome: str | None = None


class FinalResponsePayload(BaseModel):
    result: dict[str, Any] | None = None
    error: str | None = None
    summary: str | None = None
    result_card: dict[str, Any] | None = None
    explanation_context: dict[str, Any] | None = None


class ResponseProfile(BaseModel):
    effective_tone: ToneName
    effective_verbosity: VerbosityName
    effective_expertise_mode: ExpertiseMode


class ResponseProfileOverrides(BaseModel):
    tone: ToneName | None = None
    verbosity: VerbosityName | None = None
    expertise_mode: ExpertiseMode | None = None


class UserState(BaseModel):
    user_id: str
    display_name: str | None = None
    language_preference: str = "en"
    preferred_tone: ToneName = "friendly"
    expertise_level: ExpertiseMode = "beginner"
    response_verbosity: VerbosityName = "medium"


class ThreadState(BaseModel):
    thread_id: str
    message_history: list[ConversationMessage] = Field(default_factory=list)
    thread_metadata: dict[str, Any] = Field(default_factory=dict)
    latest_task_snapshot: TaskSnapshot | None = None
    artifact_references: list[ArtifactReference] = Field(default_factory=list)


class RunState(BaseModel):
    current_user_message: str
    recent_thread_history: list[ConversationMessage] = Field(default_factory=list)
    normalized_signals: dict[str, Any] = Field(default_factory=dict)
    intent: IntentName | None = None
    task_relation: TaskRelation | None = None
    requires_clarification: bool = False
    user_goal_summary: str | None = None
    candidate_strategy_draft: StrategySummary = Field(default_factory=StrategySummary)
    missing_required_fields: list[str] = Field(default_factory=list)
    optional_parameter_status: dict[str, Any] = Field(default_factory=dict)
    effective_response_profile: ResponseProfile | None = None
    confirmation_payload: ConfirmationPayload | None = None
    tool_call_records: list[ToolCallRecord] = Field(default_factory=list)
    failure_classification: str | None = None
    final_response_payload: FinalResponsePayload | None = None

    @classmethod
    def new(
        cls,
        *,
        current_user_message: str,
        recent_thread_history: list[ConversationMessage | dict[str, Any]],
    ) -> "RunState":
        return cls(
            current_user_message=current_user_message,
            recent_thread_history=deepcopy(recent_thread_history),
        )
