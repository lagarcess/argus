from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Language = Literal["en", "es-419"]
Locale = Literal["en-US", "es-419"]
Theme = Literal["dark", "light", "system"]
AssetClass = Literal["equity", "crypto"]
BacktestStatus = Literal["queued", "running", "completed", "failed"]
MessageRole = Literal["user", "assistant", "system", "tool"]
NameSource = Literal["system_default", "ai_generated", "user_renamed"]
StrategyTemplate = Literal[
    "buy_and_hold",
    "buy_the_dip",
    "rsi_mean_reversion",
    "moving_average_crossover",
    "dca_accumulation",
    "momentum_breakout",
    "trend_follow",
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

    @property
    def onboarding_incomplete(self) -> bool:
        return not self.is_onboarding_complete


class UserResponse(BaseModel):
    user: User


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
    type: Literal["chat", "strategy", "collection", "run"]
    id: str
    title: str
    matched_text: str
    updated_at: datetime
    conversation_id: str | None = None


class PaginatedSearch(BaseModel):
    items: list[SearchItem]
    next_cursor: str | None = None


class ChatStreamRequest(BaseModel):
    conversation_id: str
    message: str
    language: Language | None = None


class FeedbackRequest(BaseModel):
    type: Literal["bug", "feature", "general"]
    message: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class SignupRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    username: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class SuccessResponse(BaseModel):
    success: bool


class StarterPromptsResponse(BaseModel):
    prompts: list[str]
