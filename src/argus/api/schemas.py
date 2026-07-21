from __future__ import annotations

import json
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    WithJsonSchema,
    field_validator,
    model_validator,
)

from argus.api.feedback_context import (
    MAX_FEEDBACK_CONTEXT_DEPTH,
    MAX_FEEDBACK_CONTEXT_KEYS,
    MAX_FEEDBACK_CONTEXT_SERIALIZED_LENGTH,
    MAX_FEEDBACK_MESSAGE_LENGTH,
)
from argus.domain.capability_registry import EXECUTABLE_TEMPLATES

Language = Literal["en", "es-419"]
Locale = Literal["en-US", "es-419"]
Theme = Literal["dark", "light", "system"]
AssetClass = Literal["equity", "crypto", "currency_pair"]
BacktestStatus = Literal["queued", "running", "completed", "failed"]
BacktestJobStatus = Literal[
    "queued", "running", "succeeded", "failed", "canceled", "expired"
]
ArtifactLifecycle = Literal[
    "captured",
    "reviewed",
    "saved",
    "decided",
    "archived",
    "discarded",
]
EvidenceArtifactType = Literal["backtest"]
DecisionState = Literal["watching", "promising", "rejected", "revisit_later"]
MessageRole = Literal["user", "assistant", "system", "tool"]
NameSource = Literal["system_default", "ai_generated", "user_renamed"]
# Single source of truth: executable templates live only in the capability registry
# (derived from each StrategyCapability's status). StrategyTemplate validates against that
# set at runtime and publishes its OpenAPI enum from it, so there is no second hardcoded
# list to keep in sync. Draft templates are absent from the registry's executable set, so
# the API rejects them at the request boundary.
def _ensure_executable_template(value: str) -> str:
    if value not in EXECUTABLE_TEMPLATES:
        raise ValueError(f"unsupported strategy template: {value!r}")
    return value


StrategyTemplate = Annotated[
    str,
    AfterValidator(_ensure_executable_template),
    WithJsonSchema(
        {
            "type": "string",
            "enum": sorted(EXECUTABLE_TEMPLATES),
            "title": "StrategyTemplate",
        }
    ),
]


class OnboardingState(BaseModel):
    completed: bool = False
    stage: Literal[
        "language_selection", "primary_goal_selection", "ready", "completed"
    ] = "language_selection"
    language_confirmed: bool = False
    primary_goal: (
        Literal[
            "learn_basics",
            "build_passive_strategy",
            "test_stock_idea",
            "explore_crypto",
            "surprise_me",
        ]
        | None
    ) = None


class User(BaseModel):
    id: str
    email: str
    username: str | None = None
    display_name: str | None = None
    language: Language = "en"
    locale: Locale = "en-US"
    theme: Theme = "dark"
    is_admin: bool = False
    onboarding: OnboardingState = Field(default_factory=OnboardingState)
    created_at: datetime
    updated_at: datetime

    @property
    def is_onboarding_complete(self) -> bool:
        return self.onboarding.completed


class UserResponse(BaseModel):
    user: User


class UsageWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(ge=0)
    used: int = Field(ge=0)
    remaining: int = Field(ge=0)
    period_end: datetime


class UsageAllowance(BaseModel):
    """Backend-derived allowance truth for one resource: both active UTC
    windows plus availability and the most restrictive window."""

    model_config = ConfigDict(frozen=True)

    hour: UsageWindow
    day: UsageWindow
    available_now: bool
    limiting_window: Literal["hour", "day"]


class UsageAllowances(BaseModel):
    model_config = ConfigDict(frozen=True)

    messages: UsageAllowance
    backtests: UsageAllowance


class UsageAllowanceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowances: UsageAllowances


class ProfilePatch(BaseModel):
    display_name: str | None = None
    language: Language | None = None
    locale: Locale | None = None
    theme: Theme | None = None
    onboarding: dict[str, Any] | None = None


class ConversationCreate(BaseModel):
    title: str | None = None
    language: Language | None = None


class ConversationPatch(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    archived: bool | None = None
    deleted_at: datetime | None = None


class Conversation(BaseModel):
    id: str
    title: str
    title_source: NameSource = "system_default"
    pinned: bool = False
    archived: bool = False
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None
    language: Language | None = None


class ConversationResponse(BaseModel):
    conversation: Conversation


class Message(BaseModel):
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    created_at: datetime
    metadata: dict[str, Any] | None = None


class PaginatedMessages(BaseModel):
    items: list[Message]
    next_cursor: str | None = None


class PaginatedConversations(BaseModel):
    items: list[Conversation]
    next_cursor: str | None = None


class StrategyCreate(BaseModel):
    name: str | None = None
    template: StrategyTemplate
    asset_class: AssetClass
    symbols: list[str] = Field(min_length=1, max_length=5)
    parameters: dict[str, Any] = Field(default_factory=dict)
    metrics_preferences: list[str] = Field(
        default_factory=lambda: [
            "total_return_pct",
            "win_rate",
            "max_drawdown_pct",
        ]
    )
    benchmark_symbol: str | None = None
    conversation_id: str | None = None


class StrategyPatch(BaseModel):
    name: str | None = None
    pinned: bool | None = None
    metrics_preferences: list[str] | None = None
    parameters: dict[str, Any] | None = None
    deleted_at: datetime | None = None


class Strategy(BaseModel):
    id: str
    name: str
    name_source: NameSource
    template: StrategyTemplate
    asset_class: AssetClass
    symbols: list[str]
    parameters: dict[str, Any]
    metrics_preferences: list[str]
    benchmark_symbol: str
    pinned: bool = False
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    strategy_surface_metrics: dict[str, Any] | None = None

    @field_validator("template", mode="before")
    @classmethod
    def _tolerate_retired_template(cls, value: Any) -> Any:
        # Persisted strategies saved before a template was retired (e.g. the draft
        # momentum_breakout / trend_follow) must still load. Coerce any non-executable
        # template to buy_and_hold on read, matching the save-path fallback in
        # api/chat/strategies.strategy_template_from_run. Write models (StrategyCreate,
        # BacktestRunRequest) intentionally stay strict so the API still rejects drafts
        # at the request boundary.
        if value not in EXECUTABLE_TEMPLATES:
            return "buy_and_hold"
        return value


class StrategyResponse(BaseModel):
    strategy: Strategy


class PaginatedStrategies(BaseModel):
    items: list[Strategy]
    next_cursor: str | None = None


class CollectionCreate(BaseModel):
    name: str | None = None


class CollectionPatch(BaseModel):
    name: str | None = None
    pinned: bool | None = None


class CollectionAttach(BaseModel):
    strategy_ids: list[str]


class Collection(BaseModel):
    id: str
    name: str
    name_source: NameSource
    pinned: bool = False
    strategy_count: int = 0
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CollectionResponse(BaseModel):
    collection: Collection


class PaginatedCollections(BaseModel):
    items: list[Collection]
    next_cursor: str | None = None


class BacktestRunRequest(BaseModel):
    strategy_id: str | None = None
    conversation_id: str | None = None
    template: StrategyTemplate | None = None
    asset_class: AssetClass | None = None
    symbols: list[str] | None = None
    timeframe: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    side: Literal["long", "short", "long_short", "market_neutral"] | None = None
    starting_capital: float | None = None
    allocation_method: Literal["equal_weight"] | None = None
    parameters: dict[str, Any] | None = None
    benchmark_symbol: str | None = None


class BacktestRun(BaseModel):
    id: str
    conversation_id: str | None = None
    strategy_id: str | None = None
    status: BacktestStatus
    asset_class: AssetClass
    symbols: list[str]
    allocation_method: Literal["equal_weight"]
    benchmark_symbol: str
    metrics: dict[str, Any]
    config_snapshot: dict[str, Any]
    conversation_result_card: dict[str, Any]
    created_at: datetime
    chart: dict[str, Any] | None = None
    trades: list[dict[str, Any]] | None = None


class BacktestRunResponse(BaseModel):
    run: BacktestRun


class BacktestJob(BaseModel):
    id: str
    conversation_id: str
    request_message_id: str | None = None
    confirmation_message_id: str | None = None
    status: BacktestJobStatus
    result_run_id: str | None = None
    failure_code: str | None = None
    failure_detail: str | None = None
    retryable: bool = False
    queued_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BacktestJobResponse(BaseModel):
    job: BacktestJob
    run: BacktestRun | None = None
    result_readout: str | None = None
    result_readout_source: str | None = None
    result_readout_fallback_used: bool | None = None
    result_readout_failure_mode: str | None = None


class Idea(BaseModel):
    id: str
    source_conversation_id: str | None = None
    title: str
    summary: str
    lifecycle: ArtifactLifecycle = "captured"
    active_version_id: str | None = None
    created_at: datetime
    updated_at: datetime


class IdeaVersion(BaseModel):
    id: str
    idea_id: str
    source_conversation_id: str | None = None
    source_run_id: str | None = None
    version_number: int = 1
    canonical_spec: dict[str, Any]
    strategy_snapshot: dict[str, Any]
    title: str
    summary: str
    lifecycle: ArtifactLifecycle = "captured"
    created_at: datetime


class EvidenceArtifact(BaseModel):
    id: str
    idea_id: str
    idea_version_id: str
    source_conversation_id: str | None = None
    source_run_id: str | None = None
    artifact_type: EvidenceArtifactType = "backtest"
    lifecycle: ArtifactLifecycle = "captured"
    title: str
    digest: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DecisionNote(BaseModel):
    id: str
    idea_id: str
    idea_version_id: str
    evidence_artifact_id: str
    source_conversation_id: str | None = None
    decision_state: DecisionState
    note: str | None = None
    created_at: datetime
    updated_at: datetime


class DecisionNoteCreate(BaseModel):
    decision_state: DecisionState
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class DecisionNoteResponse(BaseModel):
    decision: DecisionNote
    evidence_artifact: EvidenceArtifact


class HistoryItem(BaseModel):
    type: Literal["chat", "strategy", "collection", "run"]
    id: str
    title: str
    subtitle: str
    pinned: bool = False
    created_at: datetime
    conversation_id: str | None = None


class PaginatedHistory(BaseModel):
    items: list[HistoryItem]
    next_cursor: str | None = None


class SearchItem(BaseModel):
    type: Literal[
        "chat",
        "strategy",
        "collection",
        "run",
        "backtest",
        "evidence",
        "decision",
        "idea",
    ]
    id: str
    title: str
    matched_text: str
    updated_at: datetime
    conversation_id: str | None = None
    lifecycle: ArtifactLifecycle | None = None
    decision_state: DecisionState | None = None
    preview: dict[str, Any] | None = None


class SearchLedgerGroup(BaseModel):
    decision_state: DecisionState
    count: int


class PaginatedSearch(BaseModel):
    items: list[SearchItem]
    next_cursor: str | None = None
    ledger_groups: list[SearchLedgerGroup] | None = None


ChatActionType = Literal[
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


class ChatActionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    type: ChatActionType
    label: str | None = None
    label_key: str | None = Field(default=None, alias="labelKey")
    payload: dict[str, Any] = Field(default_factory=dict)
    presentation: Literal["confirmation", "result"] | None = None


class ChatMentionPayload(BaseModel):
    id: str
    type: Literal["asset", "indicator"]
    label: str
    symbol: str | None = None
    asset_class: AssetClass | None = None
    description: str | None = None
    insert_text: str
    provider: str | None = None
    support_status: Literal["supported", "draft_only", "unavailable"] = "supported"


class ChatStreamRequest(BaseModel):
    conversation_id: str
    message: str | None = None
    action: ChatActionPayload | None = None
    mentions: list[ChatMentionPayload] = Field(default_factory=list)
    language: Language | None = None

    @model_validator(mode="after")
    def require_message_or_action(self) -> "ChatStreamRequest":
        if self.action is not None:
            return self
        if self.message is not None and self.message.strip():
            return self
        raise ValueError("message_or_action_required")


class DiscoveryItem(BaseModel):
    id: str
    type: Literal["asset", "indicator"]
    label: str
    symbol: str | None = None
    asset_class: AssetClass | None = None
    description: str | None = None
    insert_text: str
    provider: str
    support_status: Literal["supported", "draft_only", "unavailable"] = "supported"


class DiscoveryResponse(BaseModel):
    items: list[DiscoveryItem]


class FeedbackRequest(BaseModel):
    type: Literal["bug", "feature", "general", "account_deletion_request"]
    message: str = Field(min_length=1, max_length=MAX_FEEDBACK_MESSAGE_LENGTH)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def validate_context_bounds(cls, context: dict[str, Any]) -> dict[str, Any]:
        if len(context) > MAX_FEEDBACK_CONTEXT_KEYS:
            raise ValueError("feedback_context_too_many_keys")
        if _context_depth(context) > MAX_FEEDBACK_CONTEXT_DEPTH:
            raise ValueError("feedback_context_too_deep")
        encoded = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > MAX_FEEDBACK_CONTEXT_SERIALIZED_LENGTH:
            raise ValueError("feedback_context_too_large")
        return context


def _context_depth(value: Any) -> int:
    if isinstance(value, dict):
        if not value:
            return 1
        return 1 + max(_context_depth(item) for item in value.values())
    if isinstance(value, list):
        if not value:
            return 1
        return 1 + max(_context_depth(item) for item in value)
    return 1


class SignupRequest(BaseModel):
    email: str
    password: str
    language: Language = "en"
    display_name: str | None = None
    username: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class SuccessResponse(BaseModel):
    success: bool


class BulkConversationDeleteResponse(BaseModel):
    success: bool
    deleted_count: int


class StarterPromptsResponse(BaseModel):
    prompts: list[str]
