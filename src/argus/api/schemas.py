from __future__ import annotations

import json
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    WithJsonSchema,
    field_validator,
    model_serializer,
    model_validator,
)
from typing_extensions import NotRequired, TypedDict

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
AvatarTheme = Literal["ocean", "plum", "teal", "ember", "gold", "indigo", "slate"]
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
DecisionActionAvailability = Literal[
    "available",
    "account_conversion_required",
]
MessageRole = Literal["user", "assistant", "system", "tool"]
NameSource = Literal["system_default", "ai_generated", "user_renamed"]
ConversationOperationStatus = Literal["idle", "queued", "running", "checking"]
ConversationOperationKind = Literal["chat_turn", "backtest_job"]
ConversationAttentionStatus = Literal[
    "none",
    "new_activity",
    "manual_unread",
    "needs_input",
    "needs_attention",
]

DECISION_NOTE_WRITE_MAX_LENGTH = 500

CHAT_STREAM_MAX_BODY_BYTES = 65_536
CHAT_STREAM_MAX_CONVERSATION_ID_LENGTH = 128
CHAT_STREAM_MAX_MESSAGE_LENGTH = 16_000
CHAT_STREAM_MAX_MENTIONS = 10
CHAT_STREAM_MAX_MENTION_ID_LENGTH = 128
CHAT_STREAM_MAX_MENTION_LABEL_LENGTH = 120
CHAT_STREAM_MAX_MENTION_SYMBOL_LENGTH = 32
CHAT_STREAM_MAX_MENTION_DESCRIPTION_LENGTH = 256
CHAT_STREAM_MAX_MENTION_INSERT_TEXT_LENGTH = 64
CHAT_STREAM_MAX_MENTION_PROVIDER_LENGTH = 64
CHAT_STREAM_MAX_ACTION_LABEL_LENGTH = 120
CHAT_STREAM_MAX_ACTION_LABEL_KEY_LENGTH = 160
CHAT_STREAM_MAX_ACTION_PAYLOAD_BYTES = 16_384
CHAT_STREAM_MAX_ACTION_PAYLOAD_DEPTH = 6
CHAT_STREAM_MAX_ACTION_PAYLOAD_CONTAINER_ITEMS = 50
CHAT_STREAM_MAX_ACTION_PAYLOAD_STRING_LENGTH = 4_096


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
    """Legacy/inert compatibility state; no product behavior reads or writes it.

    The explicit onboarding flow is removed. The field survives only because
    old profile rows carry it and deployed clients may still read the `/me`
    shape during a rollout.
    """

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


PREFERRED_NAME_MAX_LENGTH = 40


def _blank_preferred_name_is_no_name(value: Any) -> Any:
    """Whitespace is not a name, and clearing the field is the way to opt out."""

    if not isinstance(value, str):
        return value
    return value.strip() or None


# Normalize first, then enforce the bound: `max_length` measures the trimmed
# value. One annotation serves the read model and the patch, so it cannot drift.
PreferredName = Annotated[
    Annotated[str, Field(max_length=PREFERRED_NAME_MAX_LENGTH)] | None,
    BeforeValidator(_blank_preferred_name_is_no_name),
]


class User(BaseModel):
    id: str
    email: str | None
    username: str | None = None
    display_name: str | None = None
    #: What the user asked Argus to call them, distinct from `display_name`,
    #: which is an identity field. Null means greetings use no name.
    preferred_name: PreferredName = None
    language: Language = "en"
    locale: Locale = "en-US"
    theme: Theme = "dark"
    avatar_theme: AvatarTheme = "ocean"
    is_admin: bool = False
    onboarding: OnboardingState = Field(default_factory=OnboardingState)
    created_at: datetime
    updated_at: datetime


class GuestAccountSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    expires_at: datetime
    conversation_id: str | None
    conversation_limit: int = Field(ge=1, le=2_147_483_647)
    message_limit: int = Field(ge=1, le=2_147_483_647)
    simulation_limit: int = Field(ge=1, le=2_147_483_647)
    feedback_limit: int = Field(ge=1, le=2_147_483_647)


class AccountCapabilities(BaseModel):
    model_config = ConfigDict(frozen=True)

    can_create_additional_conversation: bool
    can_manage_conversation: bool
    can_save_decision: bool
    can_manage_account: bool
    can_use_omnisearch: bool
    can_search_current_workspace: bool
    can_use_grounded_discovery: bool
    can_submit_feedback: bool


class GuestUser(BaseModel):
    """Guest-safe profile projection without registered-only preferences."""

    id: str
    email: str | None
    username: str | None = None
    display_name: str | None = None
    language: Language = "en"
    locale: Locale = "en-US"
    theme: Theme = "dark"
    is_admin: bool = False
    onboarding: OnboardingState = Field(default_factory=OnboardingState)
    created_at: datetime
    updated_at: datetime


def guest_safe_user(user: User) -> GuestUser:
    """Project a profile for a guest-facing response."""

    return GuestUser.model_validate(user.model_dump())


class UserResponse(BaseModel):
    user: User | GuestUser
    account_kind: Literal["guest", "registered"]
    guest: GuestAccountSummary | None
    capabilities: AccountCapabilities
    public_account_access_enabled: bool = Field(
        description="Server-authoritative permission to expose ordinary account creation."
    )

    @model_validator(mode="after")
    def _hide_registered_preferences_from_guests(self) -> UserResponse:
        if self.account_kind == "guest" and isinstance(self.user, User):
            self.user = guest_safe_user(self.user)
        return self


class UsageWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(ge=0)
    used: int = Field(ge=0)
    remaining: int = Field(ge=0)
    period_end: datetime


class UsageAllowance(BaseModel):
    """Backend-derived allowance truth for the account's active windows."""

    model_config = ConfigDict(frozen=True)

    hour: UsageWindow | None
    day: UsageWindow | None
    guest_session: UsageWindow | None
    available_now: bool
    limiting_window: Literal["hour", "day", "guest_session"]


class UsageAllowances(BaseModel):
    model_config = ConfigDict(frozen=True)

    messages: UsageAllowance
    backtests: UsageAllowance


class UsageAllowanceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowances: UsageAllowances


class ProfilePatch(BaseModel):
    display_name: str | None = None
    preferred_name: PreferredName = None
    language: Language | None = None
    locale: Locale | None = None
    theme: Theme | None = None
    avatar_theme: AvatarTheme = "ocean"


class ConversationCreate(BaseModel):
    title: str | None = None
    language: Language | None = None


class ConversationPatch(BaseModel):
    title: str | None = None
    pinned: bool | None = None
    archived: bool | None = None
    deleted_at: datetime | None = None


class ConversationOperation(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ConversationOperationStatus
    kind: ConversationOperationKind | None = None
    updated_at: datetime | None = None


class ConversationAttention(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ConversationAttentionStatus
    cursor: str | None = None


class ConversationActivity(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation: ConversationOperation
    attention: ConversationAttention


class ConversationActivityMarkUnread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["mark_unread"]


class ConversationActivityMarkRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["mark_read"]
    through_attention_cursor: str | None = Field(default=None, max_length=256)


ConversationActivityPatch = Annotated[
    ConversationActivityMarkUnread | ConversationActivityMarkRead,
    Field(discriminator="action"),
]


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
    activity: ConversationActivity | None = None


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
        # template to buy_and_hold on read. BacktestRunRequest intentionally stays
        # strict so direct execution still rejects retired drafts.
        if value not in EXECUTABLE_TEMPLATES:
            return "buy_and_hold"
        return value


class Collection(BaseModel):
    id: str
    name: str
    name_source: NameSource
    pinned: bool = False
    strategy_count: int = 0
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


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
    conversation_id: str | None = None
    request_message_id: str | None = None
    confirmation_message_id: str | None = None
    status: BacktestJobStatus
    # Absent means an ordinary backtest; 'chat.research' jobs succeed without
    # a run, so every serialized job surface must carry the scope.
    operation_scope: str | None = None
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
    next_experiments: dict[str, Any] | None = None


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
    note: str | None = Field(
        default=None,
        max_length=DECISION_NOTE_WRITE_MAX_LENGTH,
    )

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


class HistoryItemWire(TypedDict):
    type: Literal["chat", "strategy", "collection", "run"]
    id: str
    title: str
    title_source: NotRequired[NameSource]
    subtitle: str
    pinned: bool
    created_at: datetime
    conversation_id: str | None
    expires_at: datetime | None
    activity: NotRequired[ConversationActivity]


class HistoryItem(BaseModel):
    type: Literal["chat", "strategy", "collection", "run"]
    id: str
    title: str
    # Chat items only; lets clients render unnamed chats without title heuristics.
    title_source: NameSource | None = None
    subtitle: str
    pinned: bool = False
    created_at: datetime
    conversation_id: str | None = None
    expires_at: datetime | None = None
    # Chat items only; non-chat records omit the additive projection.
    activity: ConversationActivity | None = None

    @model_serializer(mode="plain", return_type=HistoryItemWire)
    def _omit_absent_chat_fields(self) -> HistoryItemWire:
        # Return Python values for Pydantic to serialize against the wire type.
        data: HistoryItemWire = {
            "type": self.type,
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "pinned": self.pinned,
            "created_at": self.created_at,
            "conversation_id": self.conversation_id,
            "expires_at": self.expires_at,
        }
        if self.title_source is not None:
            data["title_source"] = self.title_source
        if self.activity is not None:
            data["activity"] = self.activity
        return data


class PaginatedHistory(BaseModel):
    items: list[HistoryItem]
    next_cursor: str | None = None


class SearchDossierDecision(BaseModel):
    state: DecisionState
    note: str | None = Field(default=None, max_length=2000)
    run_label: str | None = Field(default=None, max_length=160)


class SearchDossierMetric(BaseModel):
    name: str = Field(max_length=80)
    value: str | int | float


class SearchDossierOutcome(BaseModel):
    run_label: str = Field(max_length=160)
    completed_at: datetime
    benchmark_symbol: str | None = Field(default=None, max_length=24)
    quick_take: str | None = Field(default=None, max_length=500)
    metrics: list[SearchDossierMetric] = Field(default_factory=list, max_length=4)


RetestDossierState = Literal["new_data_available", "no_new_data", "cant_do_it"]
RetestWindowViolationCode = Literal[
    "provider_history_start_unavailable",
    "kraken_ohlc_window_exceeded",
    "provider_timeframe_unavailable",
]


class SearchRetestRepair(BaseModel):
    kind: Literal["clamp_start"] = "clamp_start"
    start_date: date
    end_date: date


class SearchRetestAction(BaseModel):
    """Bounded typed retest envelope (spec 2.2).

    Carries identity and policy only. The executable setup is reloaded
    server-side from the owner-scoped source run, so no client value can
    reach canonical state.
    """

    type: Literal["retest_run"] = "retest_run"
    source_run_id: str
    run_label: str = Field(max_length=160)
    window_policy: Literal["preserve_start_ending_latest_available"] = (
        "preserve_start_ending_latest_available"
    )
    contract_version: Literal["argus_retest_run/v2"] = "argus_retest_run/v2"
    state: RetestDossierState
    reason_code: RetestWindowViolationCode | None = None
    repair: SearchRetestRepair | None = None

    @model_validator(mode="after")
    def validate_state_shape(self) -> SearchRetestAction:
        if self.state != "cant_do_it":
            if self.reason_code is not None or self.repair is not None:
                raise ValueError("Only cant_do_it may carry a reason or repair")
            return self
        if self.reason_code is None:
            raise ValueError("cant_do_it requires a reason_code")
        repairable = self.reason_code in {
            "provider_history_start_unavailable",
            "kraken_ohlc_window_exceeded",
        }
        if repairable != (self.repair is not None):
            raise ValueError("Retest repair must match the reason_code")
        return self


class SearchDecisionAction(BaseModel):
    type: Literal["decision"] = "decision"
    availability: DecisionActionAvailability
    evidence_artifact_id: str
    decision_state: DecisionState | None = None
    note: str | None = Field(default=None, max_length=2000)
    run_label: str = Field(max_length=160)


SearchDossierAction = Annotated[
    SearchRetestAction | SearchDecisionAction,
    Field(discriminator="type"),
]


class RunDossierTested(BaseModel):
    symbols: list[str] = Field(default_factory=list, max_length=5)
    strategy_family: str | None = Field(default=None, max_length=80)
    cadence: str | None = Field(default=None, max_length=24)
    timeframe: str | None = Field(default=None, max_length=24)
    start_date: date | None = None
    end_date: date | None = None


class RunDossier(BaseModel):
    run_id: str
    run_label: str = Field(max_length=160)
    completed_at: datetime
    result_message_id: str | None = None
    tested: RunDossierTested
    outcome: SearchDossierOutcome
    decision: SearchDossierDecision | None = None
    actions: list[SearchDossierAction] = Field(default_factory=list, max_length=2)


class PaginatedRunDossiers(BaseModel):
    items: list[RunDossier]
    next_cursor: str | None = None
    total_runs: int = Field(ge=0)
    decided_runs: int = Field(ge=0)


SearchMatchLayer = Literal[
    "conversation",
    "message",
    "run",
    "idea",
    "evidence",
    "decision",
]


class SearchMatch(BaseModel):
    layer: SearchMatchLayer
    fragment: str = Field(max_length=500)
    count: int = Field(ge=1)
    message_id: str | None = None

    @model_validator(mode="after")
    def validate_message_anchor(self) -> SearchMatch:
        if (self.layer == "message") != (self.message_id is not None):
            raise ValueError("message_id must be present only for message matches")
        return self

    @model_serializer(mode="wrap")
    def _omit_absent_message_id(self, handler: SerializerFunctionWrapHandler):
        data = handler(self)
        if data.get("message_id") is None:
            data.pop("message_id", None)
        return data


class SearchItem(BaseModel):
    type: Literal["conversation"]
    id: str
    title: str
    archived: bool
    matched_text: str
    updated_at: datetime
    conversation_id: str
    match: SearchMatch
    dossier: RunDossier | None
    total_runs: int = Field(ge=0)
    decided_runs: int = Field(ge=0)
    # Bounded conversation aggregate used for decision filters and counts.
    # The dossier separately carries the latest decision.
    decision_states: tuple[DecisionState, ...] = ()


class SearchAssetDecisionCounts(BaseModel):
    promising: int = Field(ge=0)
    watching: int = Field(ge=0)
    rejected: int = Field(ge=0)
    revisit_later: int = Field(ge=0)


class SearchAssetRollup(BaseModel):
    type: Literal["asset_rollup"] = "asset_rollup"
    symbol: str = Field(min_length=1, max_length=24)
    run_count: int = Field(ge=1)
    decision_counts: SearchAssetDecisionCounts
    last_touched_at: datetime


SearchResultItem = Annotated[
    SearchItem | SearchAssetRollup,
    Field(discriminator="type"),
]


class SearchLedgerGroup(BaseModel):
    decision_state: DecisionState
    count: int


class PaginatedSearch(BaseModel):
    items: list[SearchResultItem]
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
    "select_discovery_candidate",
    "retest_run",
]


class ChatActionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)

    type: ChatActionType
    label: str | None = Field(
        default=None, max_length=CHAT_STREAM_MAX_ACTION_LABEL_LENGTH
    )
    label_key: str | None = Field(
        default=None,
        alias="labelKey",
        max_length=CHAT_STREAM_MAX_ACTION_LABEL_KEY_LENGTH,
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    presentation: Literal["confirmation", "result"] | None = None

    @field_validator("payload")
    @classmethod
    def validate_payload_bounds(cls, payload: dict[str, Any]) -> dict[str, Any]:
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(serialized) > CHAT_STREAM_MAX_ACTION_PAYLOAD_BYTES:
            raise ValueError("action_payload_serialized_size_exceeded")
        _validate_chat_action_payload_value(payload, depth=1)
        return payload


class ChatMentionTextRange(BaseModel):
    start: int
    end: int


class ChatMentionPayload(BaseModel):
    id: str = Field(max_length=CHAT_STREAM_MAX_MENTION_ID_LENGTH)
    type: Literal["asset", "indicator"]
    label: str = Field(max_length=CHAT_STREAM_MAX_MENTION_LABEL_LENGTH)
    symbol: str | None = Field(
        default=None,
        max_length=CHAT_STREAM_MAX_MENTION_SYMBOL_LENGTH,
    )
    asset_class: AssetClass | None = None
    description: str | None = Field(
        default=None,
        max_length=CHAT_STREAM_MAX_MENTION_DESCRIPTION_LENGTH,
    )
    insert_text: str = Field(max_length=CHAT_STREAM_MAX_MENTION_INSERT_TEXT_LENGTH)
    provider: str | None = Field(
        default=None,
        max_length=CHAT_STREAM_MAX_MENTION_PROVIDER_LENGTH,
    )
    message_range: ChatMentionTextRange | None = None
    support_status: Literal["supported", "draft_only", "unavailable"] = "supported"

    @field_validator("message_range", mode="before")
    @classmethod
    def discard_malformed_message_range(cls, value: Any) -> Any:
        if isinstance(value, ChatMentionTextRange):
            start, end = value.start, value.end
        elif isinstance(value, dict):
            start, end = value.get("start"), value.get("end")
        else:
            return None
        if (
            not isinstance(start, int)
            or isinstance(start, bool)
            or not isinstance(end, int)
            or isinstance(end, bool)
            or start < 0
            or end < start
        ):
            return None
        return {"start": start, "end": end}


class ChatStreamRequest(BaseModel):
    conversation_id: str = Field(max_length=CHAT_STREAM_MAX_CONVERSATION_ID_LENGTH)
    message: str | None = Field(default=None, max_length=CHAT_STREAM_MAX_MESSAGE_LENGTH)
    action: ChatActionPayload | None = None
    mentions: list[ChatMentionPayload] = Field(
        default_factory=list,
        max_length=CHAT_STREAM_MAX_MENTIONS,
    )
    language: Language | None = None
    # Temporary chat: the client may opt a conversation out of memory. Opting
    # out only ever disables recall and proposals; it grants nothing.
    memory_opt_out: bool = False
    # Width band the turn was sent from. Narrow shortens generated titles at
    # the point of generation; the client never clips what it is given.
    viewport: Literal["narrow", "wide"] | None = None

    @model_validator(mode="after")
    def require_message_or_action(self) -> "ChatStreamRequest":
        if self.action is not None:
            return self
        if self.message is not None and self.message.strip():
            return self
        raise ValueError("message_or_action_required")


from argus.api.confirmation_schemas import (  # noqa: E402, F401 — re-exported API surface
    ConfirmationDirectEditRequest,
    ConfirmationDirectEditWindow,
    ConfirmationPeerAssetsRequest,
)


class ConfirmationPeerAssetsResponse(BaseModel):
    message: Message


class ConfirmationDirectEditResponse(BaseModel):
    message: Message


def _validate_chat_action_payload_value(value: Any, *, depth: int) -> None:
    if isinstance(value, dict):
        if depth > CHAT_STREAM_MAX_ACTION_PAYLOAD_DEPTH:
            raise ValueError("action_payload_depth_exceeded")
        if len(value) > CHAT_STREAM_MAX_ACTION_PAYLOAD_CONTAINER_ITEMS:
            raise ValueError("action_payload_object_keys_exceeded")
        for nested in value.values():
            _validate_chat_action_payload_value(nested, depth=depth + 1)
        return
    if isinstance(value, list):
        if depth > CHAT_STREAM_MAX_ACTION_PAYLOAD_DEPTH:
            raise ValueError("action_payload_depth_exceeded")
        if len(value) > CHAT_STREAM_MAX_ACTION_PAYLOAD_CONTAINER_ITEMS:
            raise ValueError("action_payload_array_items_exceeded")
        for nested in value:
            _validate_chat_action_payload_value(nested, depth=depth + 1)
        return
    if (
        isinstance(value, str)
        and len(value) > CHAT_STREAM_MAX_ACTION_PAYLOAD_STRING_LENGTH
    ):
        raise ValueError("action_payload_string_length_exceeded")


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


class MarketSession(BaseModel):
    """Which session US equities are in, resolved in Eastern time."""

    model_config = ConfigDict(frozen=True)

    phase: Literal[
        "pre_market",
        "open",
        "after_hours",
        "closed_weekend",
        "closed_holiday",
        "closed",
    ]
    is_market_day: bool
    as_of: datetime


class MarketSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    session: MarketSession | None = Field(
        description=(
            "Null when the trading calendar is unreachable. Callers say nothing "
            "about the market rather than guessing an open or a holiday."
        )
    )


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
    captcha_token: str = Field(min_length=1, max_length=4096)
    language: Language = "en"
    display_name: str | None = None
    username: str | None = None

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        return normalized or None


class LoginRequest(BaseModel):
    email: str
    password: str
    captcha_token: str = Field(min_length=1, max_length=4096)


class AccessRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str = Field(min_length=3, max_length=320)
    language: Language

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            "@" not in normalized
            or normalized.startswith("@")
            or normalized.endswith("@")
            or any(character.isspace() for character in normalized)
        ):
            raise ValueError("invalid_email")
        return normalized


class AccessRequestAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: Literal[True]


class AccessApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            "@" not in normalized
            or normalized.startswith("@")
            or normalized.endswith("@")
            or any(character.isspace() for character in normalized)
        ):
            raise ValueError("invalid_email")
        return normalized


class AccessApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    approved: Literal[True] = True


class GuestBootstrapRequest(BaseModel):
    captcha_token: str = Field(min_length=1, max_length=4096)
    language: Language = "en"


GuestHandoffKind = Literal["existing_account", "new_account_signup"]


GuestConversionReason = Literal[
    "second_simulation",
    "simulation_limit",
    "message_limit",
    "save_decision",
    "new_conversation",
    "keep_history",
    "discovery_searches",
]


class GuestPendingAction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: GuestConversionReason
    conversation_id: str = Field(min_length=1, max_length=128)
    action_id: str = Field(min_length=1, max_length=128)
    artifact_id: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def require_reason_specific_identity(self) -> "GuestPendingAction":
        if self.reason == "save_decision" and self.artifact_id is None:
            raise ValueError("save_decision_requires_artifact_id")
        if self.reason != "save_decision" and self.artifact_id is not None:
            raise ValueError("artifact_id_is_only_valid_for_save_decision")
        return self


class GuestHandoffCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    handoff_kind: GuestHandoffKind = "existing_account"
    destination_email: str = Field(min_length=3, max_length=320)
    source_conversation_id: str = Field(min_length=1, max_length=128)
    pending_action: GuestPendingAction | None = None

    @field_validator("destination_email")
    @classmethod
    def normalize_destination_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            "@" not in normalized
            or normalized.startswith("@")
            or normalized.endswith("@")
            or any(character.isspace() for character in normalized)
        ):
            raise ValueError("invalid_email")
        return normalized

    @model_validator(mode="after")
    def bind_action_to_source_conversation(self) -> "GuestHandoffCreateRequest":
        if (
            self.pending_action is not None
            and self.pending_action.conversation_id != self.source_conversation_id
        ):
            raise ValueError("pending_action_conversation_mismatch")
        return self


class GuestHandoffCreateResponse(BaseModel):
    handoff_id: str
    expires_at: datetime


class GuestHandoffClaimResponse(BaseModel):
    conversation_id: str
    pending_action: GuestPendingAction | None = None


class GuestAccountSignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    captcha_token: str = Field(min_length=1, max_length=4096, repr=False)
    language: Language = "en"
    display_name: str | None = None
    username: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if (
            "@" not in normalized
            or normalized.startswith("@")
            or normalized.endswith("@")
            or any(character.isspace() for character in normalized)
        ):
            raise ValueError("invalid_email")
        return normalized

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().casefold()
        return normalized or None


class GuestFunnelClientEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event: Literal["starter_action_selected", "conversion_prompt_shown"]
    language: Language
    surface: Literal["starter_actions", "conversion_modal"]
    strategy_category: Literal["buy_and_hold", "dca_accumulation"] | None = None
    conversion_reason: GuestConversionReason | None = None
    terminal_outcome: Literal["selected", "shown"]

    @model_validator(mode="after")
    def require_event_specific_properties(self) -> "GuestFunnelClientEventRequest":
        if self.event == "starter_action_selected":
            if (
                self.surface != "starter_actions"
                or self.strategy_category is None
                or self.conversion_reason is not None
                or self.terminal_outcome != "selected"
            ):
                raise ValueError("invalid_starter_action_event")
        elif (
            self.surface != "conversion_modal"
            or self.conversion_reason is None
            or self.strategy_category is not None
            or self.terminal_outcome != "shown"
        ):
            raise ValueError("invalid_conversion_prompt_event")
        return self


class SuccessResponse(BaseModel):
    success: bool


class BulkConversationDeleteResponse(BaseModel):
    success: bool
    deleted_count: int


class StarterPromptsResponse(BaseModel):
    prompts: list[str]
