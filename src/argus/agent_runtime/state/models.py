from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_serializer,
    model_validator,
)

ToneName = Literal["friendly", "concise"]
VerbosityName = Literal["low", "medium", "high"]
ExpertiseMode = Literal["beginner", "intermediate", "advanced"]
MessageRole = Literal["user", "assistant", "system", "tool"]
FieldExtractionStatus = Literal["resolved", "missing", "ambiguous", "unsupported"]
ResolutionStatus = Literal[
    "resolved",
    "ambiguous",
    "unsupported",
    "unavailable_for_requested_run",
]
ResolutionSource = Literal["llm_extraction", "user_mention"]
ResolutionCandidateKind = Literal["asset", "indicator"]
ResolutionConfidence = Literal["high", "medium", "low"]
PendingNeedName = Literal[
    "asset_target",
    "sizing_amount",
    "schedule",
    "period",
    "rule_definition",
    "assumption",
    "simplification_choice",
    "refinement",
]

ResponseIntentKind = Literal[
    "clarification",
    "beginner_guidance",
    "coverage_recovery",
    "unsupported_recovery",
    "ambiguity_check",
    "optional_settings",
    "artifact_action_recovery",
    "result_followup_chrome",
]

ArtifactActionRecoveryAction = Literal["retry_failed_action"]
ArtifactActionRecoveryStatus = Literal[
    "stale",
    "missing_artifact_id",
    "missing_payload",
    "non_retryable",
    "rebuilt_confirmation",
]

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
            {
                key: freeze_state_payload(nested_value)
                for key, nested_value in value.items()
            }
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


def thaw_state_payload(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {
            key: thaw_state_payload(nested_value) for key, nested_value in value.items()
        }
    if isinstance(value, dict):
        return {
            key: thaw_state_payload(nested_value) for key, nested_value in value.items()
        }
    if isinstance(value, list | tuple):
        return [thaw_state_payload(item) for item in value]
    if isinstance(value, set | frozenset):
        return [thaw_state_payload(item) for item in value]
    return deepcopy(value)


class ConversationMessage(BaseModel):
    role: MessageRole
    content: str


class StrategySummary(BaseModel):
    raw_user_phrasing: str | None = None
    strategy_type: str | None = None
    strategy_thesis: str | None = None
    asset_universe: list[str] = Field(default_factory=list)
    asset_class: str | None = None
    timeframe: str | None = None
    cadence: str | None = None
    entry_logic: str | None = None
    exit_logic: str | None = None
    date_range: str | dict[str, Any] | None = None
    sizing_mode: str | None = None
    capital_amount: float | None = None
    position_size: float | None = None
    risk_rules: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    comparison_baseline: str | None = None
    refinement_of: str | None = None
    entry_rule: dict[str, Any] | None = None
    exit_rule: dict[str, Any] | None = None
    rule_spec: dict[str, Any] | None = None
    resolution_provenance: list["ResolutionProvenance"] = Field(default_factory=list)
    extra_parameters: dict[str, Any] = Field(default_factory=dict)

    @field_serializer("resolution_provenance")
    def serialize_resolution_provenance(self, value: list[Any]) -> list[dict[str, Any]]:
        return [
            item.model_dump(mode="python")
            for item in dedupe_resolution_provenance_items(value)
        ]


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
        return thaw_state_payload(value)


class UnsupportedConstraint(BaseModel):
    category: str
    raw_value: str
    explanation: str
    simplification_options: list[SimplificationOption] = Field(default_factory=list)


class ResolutionProvenance(BaseModel):
    field: str
    raw_text: str
    source: ResolutionSource
    candidate_kind: ResolutionCandidateKind
    resolution_status: ResolutionStatus = "resolved"
    canonical_symbol: str | None = None
    asset_class: str | None = None
    validated_by: str | None = None
    confidence: ResolutionConfidence | None = None


def normalize_resolution_provenance_items(
    items: list[ResolutionProvenance | dict[str, Any]] | tuple[Any, ...] | None,
) -> list[ResolutionProvenance]:
    normalized: list[ResolutionProvenance] = []
    for raw_item in items or []:
        if isinstance(raw_item, ResolutionProvenance):
            normalized.append(raw_item)
            continue
        try:
            normalized.append(ResolutionProvenance.model_validate(raw_item))
        except (TypeError, ValueError, ValidationError):
            continue
    return normalized


def dedupe_resolution_provenance_items(
    items: list[ResolutionProvenance | dict[str, Any]] | tuple[Any, ...] | None,
) -> list[ResolutionProvenance]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[ResolutionProvenance] = []
    for item in normalize_resolution_provenance_items(items):
        key = (item.field, item.raw_text, item.source, item.candidate_kind)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


class ResponseIntent(BaseModel):
    kind: ResponseIntentKind
    semantic_needs: list[PendingNeedName] = Field(default_factory=list)
    requested_fields: list[str] = Field(default_factory=list)
    facts: dict[str, Any] = Field(default_factory=dict)
    options: list[dict[str, Any]] = Field(default_factory=list)


class ArtifactActionRecoveryFacts(BaseModel):
    action_type: ArtifactActionRecoveryAction
    status: ArtifactActionRecoveryStatus
    requested_failed_action_id: str | None = None
    latest_failed_action_id: str | None = None
    user_safe_message: str | None = None


class ArtifactReference(BaseModel):
    artifact_kind: str
    artifact_id: str
    artifact_status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


StructuredActionType = Literal[
    "run_backtest",
    "change_dates",
    "change_asset",
    "adjust_assumptions",
    "cancel_confirmation",
    "show_breakdown",
    "refine_strategy",
    "save_strategy",
    "retry_failed_action",
    "select_response_option",
]


class StructuredActionContext(BaseModel):
    type: StructuredActionType
    label: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    presentation: Literal["confirmation", "result"] | None = None

    @property
    def failed_action_artifact_id(self) -> str | None:
        if self.type != "retry_failed_action":
            return None
        raw_value = self.payload.get("failed_action_id")
        if not isinstance(raw_value, str):
            return None
        artifact_id = raw_value.strip()
        return artifact_id or None


class TaskSnapshot(BaseModel):
    latest_task_type: IntentName | None = None
    completed: bool | None = None
    pending_strategy_summary: StrategySummary | None = None
    confirmed_strategy_summary: StrategySummary | None = None
    pending_needs: list[PendingNeedName] = Field(default_factory=list)
    field_provenance: dict[str, str] = Field(default_factory=dict)
    resolution_provenance: list[ResolutionProvenance] = Field(default_factory=list)
    active_draft_reference: ArtifactReference | None = None
    active_confirmation_reference: ArtifactReference | None = None
    latest_backtest_result_reference: ArtifactReference | None = None
    latest_collection_action_reference: ArtifactReference | None = None
    latest_failed_action_reference: ArtifactReference | None = None
    saved_strategy_reference: ArtifactReference | None = None
    artifact_references: list[ArtifactReference] = Field(default_factory=list)
    last_unresolved_follow_up: str | None = None


class ConfirmationPayload(BaseModel):
    strategy: StrategySummary
    optional_parameters: dict[str, Any] = Field(default_factory=dict)
    launch_payload: dict[str, Any] | None = None
    validation: dict[str, Any] = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
    tool_name: str
    payload: dict[str, Any] = Field(default_factory=dict)
    outcome: str | None = None


class FinalResponsePayload(BaseModel):
    result: dict[str, Any] | None = None
    backtest_job: dict[str, Any] | None = None
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
    requested_field: str | None = None
    optional_parameter_status: dict[str, Any] = Field(default_factory=dict)
    effective_response_profile: ResponseProfile | None = None
    confirmation_payload: ConfirmationPayload | None = None
    tool_call_records: list[ToolCallRecord] = Field(default_factory=list)
    failure_classification: str | None = None
    final_response_payload: FinalResponsePayload | None = None
    response_intent: ResponseIntent | None = None
    semantic_turn_act: str | None = None
    context_hints: list[ResolutionProvenance] = Field(default_factory=list)
    resolution_provenance: list[ResolutionProvenance] = Field(default_factory=list)
    structured_action: StructuredActionContext | None = None

    @classmethod
    def new(
        cls,
        *,
        current_user_message: str,
        recent_thread_history: list[ConversationMessage | dict[str, Any]],
        context_hints: list[ResolutionProvenance | dict[str, Any]] | None = None,
        action_context: StructuredActionContext | dict[str, Any] | None = None,
    ) -> "RunState":
        structured_action = (
            StructuredActionContext.model_validate(action_context)
            if action_context is not None
            else None
        )
        return cls(
            current_user_message=current_user_message,
            recent_thread_history=deepcopy(recent_thread_history),
            context_hints=[
                ResolutionProvenance.model_validate(hint)
                for hint in (context_hints or [])
            ],
            structured_action=structured_action,
        )
