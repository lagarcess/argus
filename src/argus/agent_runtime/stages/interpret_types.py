from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from argus.agent_runtime.recovery_messages import recovery_state_from_text
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.state.models import (
    AmbiguousField,
    IntentName,
    ResolutionProvenance,
    ResponseProfile,
    ResponseProfileOverrides,
    StrategySummary,
    TaskRelation,
    TaskSnapshot,
    UnsupportedConstraint,
    UserState,
    dedupe_resolution_provenance_items,
)
from pydantic import BaseModel, Field

StageOutcome = Literal[
    "needs_clarification",
    "ready_for_confirmation",
    "await_user_reply",
    "await_approval",
    "approved_for_execution",
    "execution_succeeded",
    "execution_failed_recoverably",
    "execution_failed_terminally",
    "ready_to_respond",
    "end_run",
]
ArbitrationMode = Literal["deterministic", "structured_arbitration"]
SemanticTurnAct = Literal[
    "new_idea",
    "answer_pending_need",
    "refine_current_idea",
    "educational_question",
    "result_followup",
    "retry_failed_action",
    "approval",
    "unsupported_request",
    "asset_discovery",
]
AssetDiscoveryRelationship = Literal["category", "peer", "comparison"]
ResultFollowupFocus = Literal[
    "why_underperformed",
    "max_drawdown",
    "drawdown_date",
    "peak_date",
    "peak_value",
    "result_card_fact",
    "what_tested",
    "next_experiment",
    "assumptions",
    "general",
]
CapabilityQuestionFocus = Literal[
    "supported_strategies",
    "supported_indicators",
    "limits",
    "assets",
    "general",
]
ContextQuestionFocus = Literal[
    "macro_context",
    "corporate_events",
    "market_movers",
]
ArtifactTarget = Literal[
    "none",
    "active_confirmation",
    "pending_refinement",
    "latest_result",
]


class AssetDiscoveryRequest(BaseModel):
    """Typed payload for an explicit peer/category asset-discovery request."""

    relationship: AssetDiscoveryRelationship = Field(
        description=(
            "Classify the user's discovery goal: comparison when the user's goal "
            "is choosing what to compare against an anchor, even when the "
            "comparison candidates share a category; peer for assets similar to "
            "an anchor; category only when the category itself is the discovery "
            "goal and no comparison anchor is requested."
        )
    )
    category_description: str | None = Field(default=None, max_length=200)
    anchor_symbols: list[str] = Field(default_factory=list, max_length=5)
    asset_class_hint: Literal["equity", "crypto", "currency_pair"] | None = None
    needs_current_facts: bool = Field(
        default=False,
        description=(
            "True only when a correct answer requires facts newer than model "
            "knowledge -- recent IPOs, this week's movers, current rankings, "
            "anything whose right answer changes with time -- when the user "
            "asks for current or up-to-date candidates, or explicitly asks to "
            "search current sources, in any language. False for stable "
            "relationships: sectors, categories, peers, 'names like X'. Judge "
            "the answer, not the wording."
        ),
    )


class InterpretDecision(BaseModel):
    intent: IntentName
    task_relation: TaskRelation
    requires_clarification: bool
    user_goal_summary: str
    candidate_strategy_draft: StrategySummary = Field(default_factory=StrategySummary)
    detected_user_language: str | None = None
    missing_required_fields: list[str] = Field(default_factory=list)
    optional_parameter_opportunity: list[str] = Field(default_factory=list)
    confidence: float
    arbitration_mode: ArbitrationMode = "structured_arbitration"
    reason_codes: list[str] = Field(default_factory=list)
    effective_response_profile: ResponseProfile
    user_preference_overridden_for_turn: bool = False
    normalized_signals: dict[str, Any] = Field(default_factory=dict)
    ambiguous_fields: list[AmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[UnsupportedConstraint] = Field(default_factory=list)
    resolution_provenance: list[ResolutionProvenance] = Field(default_factory=list)
    semantic_turn_act: SemanticTurnAct | None = None
    result_followup_focus: ResultFollowupFocus | None = None
    result_followup_fact_key: str | None = None
    capability_question_focus: CapabilityQuestionFocus | None = None
    context_question_focus: ContextQuestionFocus | None = None
    artifact_target: ArtifactTarget | None = None
    asset_discovery: AssetDiscoveryRequest | None = None

    def to_patch(self) -> dict[str, Any]:
        ambiguous = [item.model_dump(mode="python") for item in self.ambiguous_fields]
        unsupported = [
            item.model_dump(mode="python") for item in self.unsupported_constraints
        ]
        resolution_provenance = [
            item.model_dump(mode="python")
            for item in dedupe_resolution_provenance_items(self.resolution_provenance)
        ]
        return {
            "normalized_signals": self.normalized_signals,
            "intent": self.intent,
            "task_relation": self.task_relation,
            "requires_clarification": self.requires_clarification,
            "user_goal_summary": self.user_goal_summary,
            "detected_user_language": self.detected_user_language,
            "candidate_strategy_draft": self.candidate_strategy_draft.model_dump(
                mode="python"
            ),
            "missing_required_fields": list(self.missing_required_fields),
            "optional_parameter_status": {
                "optional_parameter_opportunity": list(
                    self.optional_parameter_opportunity
                ),
                "user_preference_overridden_for_turn": (
                    self.user_preference_overridden_for_turn
                ),
                "confidence": self.confidence,
                "arbitration_mode": self.arbitration_mode,
                "ambiguous_fields": ambiguous,
                "unsupported_constraints": unsupported,
            },
            "effective_response_profile": self.effective_response_profile,
            "reason_codes": list(self.reason_codes),
            "ambiguous_fields": ambiguous,
            "unsupported_constraints": unsupported,
            "resolution_provenance": resolution_provenance,
            "semantic_turn_act": self.semantic_turn_act,
            "result_followup_focus": self.result_followup_focus,
            "result_followup_fact_key": self.result_followup_fact_key,
            "capability_question_focus": self.capability_question_focus,
            "context_question_focus": self.context_question_focus,
            "asset_discovery": (
                None
                if self.asset_discovery is None
                else self.asset_discovery.model_dump(mode="python")
            ),
        }


class StageResult(BaseModel):
    outcome: StageOutcome
    decision: InterpretDecision | None = None
    stage_patch: dict[str, Any] = Field(default_factory=dict)

    @property
    def patch(self) -> dict[str, Any]:
        patch = dict(self.stage_patch)
        if self.decision is not None:
            patch = {**self.decision.to_patch(), **patch}
        if "recovery" not in patch:
            recovery = recovery_state_from_text(
                patch.get("assistant_response") or patch.get("assistant_prompt")
            )
            if recovery is not None:
                patch["recovery"] = recovery
        return patch


class StructuredInterpretation(BaseModel):
    research_query: ResearchQueryExtraction | None = None
    intent: IntentName
    task_relation: TaskRelation
    requires_clarification: bool = False
    user_goal_summary: str
    detected_user_language: str | None = None
    candidate_strategy_draft: StrategySummary = Field(default_factory=StrategySummary)
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    confidence: float = 0.8
    reason_codes: list[str] = Field(default_factory=list)
    ambiguous_fields: list[AmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[UnsupportedConstraint] = Field(default_factory=list)
    response_profile_overrides: ResponseProfileOverrides = Field(
        default_factory=ResponseProfileOverrides
    )
    semantic_turn_act: SemanticTurnAct | None = None
    result_followup_focus: ResultFollowupFocus | None = None
    result_followup_fact_key: str | None = None
    capability_question_focus: CapabilityQuestionFocus | None = None
    context_question_focus: ContextQuestionFocus | None = None
    artifact_target: ArtifactTarget | None = None
    asset_discovery: AssetDiscoveryRequest | None = None


class InterpretationRequest(BaseModel):
    current_user_message: str
    recent_thread_history: list[Any] = Field(default_factory=list)
    latest_task_snapshot: TaskSnapshot | None = None
    selected_thread_metadata: dict[str, Any] = Field(default_factory=dict)
    user: UserState


@runtime_checkable
class StructuredInterpreter(Protocol):
    def __call__(
        self,
        request: InterpretationRequest,
    ) -> StructuredInterpretation | None: ...

    async def ainvoke(
        self,
        request: InterpretationRequest,
    ) -> StructuredInterpretation | None: ...
