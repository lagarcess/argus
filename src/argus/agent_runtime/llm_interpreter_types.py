from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal, Union

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    create_model,
    model_validator,
)
from pydantic.json_schema import SkipJsonSchema

from argus.agent_runtime.state.models import (
    CanonicalIntentName,
    IntentName,
    normalize_legacy_interpretation,
)
from argus.domain.tool_contracts import MAX_TOOL_CALLS, ToolCall

if TYPE_CHECKING:
    from argus.domain.tool_declaration import ToolCatalog, ToolDeclaration
from argus.agent_runtime.backtest_input import (
    BacktestStrategyInput,
    LLMDateRangeIntent,  # noqa: F401 - historical import path
    LLMRiskRule,  # noqa: F401 - historical import path
)
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret_types import (
    ArtifactTarget,
    AssetDiscoveryRequest,
    CapabilityQuestionFocus,
    ContextQuestionFocus,
    ResultFollowupFocus,
)
from argus.agent_runtime.state.models import ResponseProfileOverrides


class InterpretationContractError(ValueError):
    """A model response the runtime cannot act on.

    Distinct from a transport or schema failure: the provider answered, and this
    rejection is a pure function of (response, request), so repeating the same
    call reproduces it exactly.
    """

    def __init__(self, reason: str, *, corrective_hint: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.corrective_hint = corrective_hint


class LLMAssetMentionCandidate(BaseModel):
    raw_text: str = Field(
        default="",
        description=(
            "Exact short user-message span that names a possible traded asset, "
            "company, ticker, crypto asset, currency pair, benchmark, or "
            "comparison asset."
        ),
    )
    role: Literal["traded_asset", "benchmark", "unknown"] = Field(
        default="unknown",
        description=(
            "Use traded_asset when the user wants to buy, hold, test, or include "
            "the asset in the strategy. Use benchmark when it is only a comparison "
            "or reference baseline."
        ),
    )
    mention_kind: Literal[
        "company_name",
        "ticker",
        "crypto",
        "currency_pair",
        "unknown",
    ] = Field(
        default="unknown",
        description=(
            "Classify the raw span itself. Use company_name for public company "
            "names like Target or Costco, ticker for stock symbols like TGT or "
            "AAPL, crypto for assets like Bitcoin, and currency_pair for FX pairs."
        ),
    )
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class LLMAssetMentionExtraction(BaseModel):
    asset_mentions: list[LLMAssetMentionCandidate] = Field(
        default_factory=list,
        max_length=6,
        description=(
            "Provider-resolution candidates identified by the LLM from the current "
            "message. Keep at most six distinct asset-like mentions."
        ),
    )
    all_traded_asset_mentions_included: bool = Field(
        description=(
            "True only when every traded-asset or unknown asset-like mention in "
            "the current message is present in asset_mentions. Set false when the "
            "six-item limit omits any such mention."
        )
    )


class LLMStrategyDraft(BacktestStrategyInput):
    # Only deterministic runtime code can write this channel; model output cannot
    # reach a private attribute. A str span is fidelity-audit evidence bound to a
    # quote from the current message; a None span is typed edit-plan evidence,
    # which has no bounded quote.
    _validated_execution_cost_evidence: dict[str, tuple[float, str | None]] = PrivateAttr(
        default_factory=dict
    )

    @model_validator(mode="before")
    @classmethod
    def read_legacy_extension_fields(cls, value: Any) -> Any:
        """Pending drafts keep their historical top-level field ownership."""
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        extra = dict(payload.get("extra_parameters") or {})
        for name, field in cls.model_fields.items():
            metadata = field.json_schema_extra
            if isinstance(metadata, dict) and metadata.get("x-argus-runtime-extension"):
                if payload.get(name) is not None:
                    extra[name] = payload[name]
        payload["extra_parameters"] = extra
        return payload


class LLMSimplificationOption(BaseModel):
    label: str
    replacement_values: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Canonical action payload for this simplification option. Labels are "
            "display text only; executable recovery must use this structured "
            "payload, for example {'strategy_type': 'buy_and_hold'}."
        ),
    )


class LLMUnsupportedConstraint(BaseModel):
    category: str
    raw_value: str
    explanation: str
    simplification_options: list[LLMSimplificationOption] = Field(
        default_factory=list,
        description=(
            "Language-neutral simplification actions. Populate replacement_values "
            "with the canonical payload; keep label as display text."
        ),
    )
    simplification_labels: list[str] = Field(default_factory=list)


class LLMAmbiguousField(BaseModel):
    field_name: str
    raw_value: str
    candidate_normalized_value: Any | None = None
    reason_code: str


class LLMInterpretationResponse(BaseModel):
    _tool_asset_resolution_context: str | None = PrivateAttr(default=None)
    uses_tool_catalog: ClassVar[bool] = False
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=MAX_TOOL_CALLS)
    _read_legacy_intent = model_validator(mode="before")(normalize_legacy_interpretation)

    @model_validator(mode="after")
    def tool_call_ids_are_distinct(self) -> LLMInterpretationResponse:
        call_ids = [call.call_id for call in self.tool_calls]
        if len(call_ids) != len(set(call_ids)):
            raise ValueError("Tool calls in a turn must have distinct call_id values")
        if self.tool_calls and self.candidate_strategy_draft.model_dump(
            exclude_defaults=True
        ):
            raise ValueError(
                "A tool call owns its arguments; a second strategy draft is not allowed"
            )
        return self

    intent: IntentName
    task_relation: Literal["new_task", "continue", "refine", "ambiguous"]
    requires_clarification: bool = False
    user_goal_summary: str
    detected_user_language: str | None = Field(
        default=None,
        description=(
            "Detected language of the current user message as a BCP-47-style code "
            "such as en, es, or es-419. Populate this for every turn; it is typed "
            "turn metadata, not an executable strategy field."
        ),
    )
    candidate_strategy_draft: LLMStrategyDraft = Field(
        default_factory=LLMStrategyDraft,
        description=(
            "Pending historical-test input when no tool call is emitted. Preserve "
            "known assets, dates, money roles and unsupported rule meaning here "
            "when a requested historical test cannot yet execute. A refusal must "
            "not discard the user's remaining test context. Leave empty when calls "
            "own their typed inputs or when the request is unrelated to a test."
        ),
    )
    research_query: ResearchQueryExtraction | None = Field(
        default=None,
        description=(
            "Populate the question shape and subjects here for finance questions, "
            "including named comparisons and asset discovery. This primary "
            "interpretation owns the research route; no later model reclassifies "
            "the message. Leave candidate_strategy_draft empty for research. "
            "Leave research_query null for build/run requests, replies to a pending "
            "setup question, edits, approvals, and questions about a visible result "
            "or confirmation. A named comparison is research unless the user asks "
            "to simulate an investment or strategy."
        ),
    )
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    uses_latest_result_context: bool | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    ambiguous_fields: list[LLMAmbiguousField] = Field(default_factory=list)
    unsupported_constraints: list[LLMUnsupportedConstraint] = Field(default_factory=list)
    response_profile_overrides: ResponseProfileOverrides = Field(
        default_factory=ResponseProfileOverrides
    )
    semantic_turn_act: (
        Literal[
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
        | None
    ) = None
    asset_discovery: AssetDiscoveryRequest | None = Field(
        default=None,
        description=(
            "Independent of semantic_turn_act, answer one extra question for "
            "every turn: does the user ask Argus to find, discover, list, or "
            "search for which assets exist — by category ('what cybersecurity "
            "stocks could I test?', 'find me cryptos that are trending'), by "
            "peer similarity ('companies like Nvidia'), or for comparison "
            "candidates ('what else in Costco's category could I compare?'), "
            "in any language? If yes, fill this payload even when the turn is "
            "also a question and you chose educational_question or another "
            "act; the runtime routes discovery from this payload, not from "
            "the act label. Set relationship to category, peer, or "
            "comparison; put the plain category phrase in "
            "category_description; put known anchor tickers in "
            "anchor_symbols; leave candidate_strategy_draft empty for these "
            "turns. Leave this null for ordinary 'what should I try next?' "
            "follow-ups, for questions about whether Argus supports finding "
            "assets, and for direct requests to test a named asset."
        ),
    )
    result_followup_focus: ResultFollowupFocus | None = None
    result_followup_fact_key: str | None = Field(
        default=None,
        description=(
            "Canonical snake_case key for the single factual latest-result value "
            "the user asked about. Known keys: total_return, benchmark_return, "
            "benchmark_delta, benchmark_symbol, max_drawdown, drawdown_date, "
            "peak_date, peak_value, lowest_date, lowest_value, final_value, "
            "annualized_return, profit, volatility, win_rate, profit_factor, "
            "sharpe_ratio, trade_count, starting_capital, date_range, symbols, "
            "strategy. For another single result metric, emit its plain "
            "snake_case name (for example sortino_ratio) — never a sentence or "
            "synonym phrase. Leave unset when the question is not about one "
            "specific result value. Use this only with "
            "semantic_turn_act=result_followup."
        ),
    )
    capability_question_focus: CapabilityQuestionFocus | None = Field(
        default=None,
        description=(
            "Set the relevant scope when the user asks which Argus operations or "
            "assets are available. The answer is composed from the effective "
            "tool catalog. This is capability discovery, not a tool dispatch."
        ),
    )
    context_question_focus: ContextQuestionFocus | None = None
    artifact_target: ArtifactTarget | None = None


class FocusedStrategyExtraction(BacktestStrategyInput):
    is_testable_strategy: bool
    requires_clarification: bool = False
    user_goal_summary: str
    missing_required_fields: list[str] = Field(default_factory=list)
    assistant_response: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class FocusedDateWindowExtraction(BaseModel):
    has_date_window: bool = Field(
        description=(
            "True when the current user message states a backtest date window, "
            "lookback window, start/end date, or other temporal constraint."
        )
    )
    date_range_raw_text: str | None = Field(
        default=None,
        description=(
            "Shortest exact user-message span that expresses the temporal window. "
            "Keep the user's language; this is provenance, not executable input."
        ),
    )
    date_range_intent: LLMDateRangeIntent | None = Field(
        default=None,
        description=(
            "Canonical language-neutral temporal intent. Required for relative or "
            "semantic windows. A present-anchored lookback duration is complete "
            "without explicit calendar endpoints. Do not calculate endpoint dates "
            "for relative windows."
        ),
    )
    date_range: dict[str, str] | None = Field(
        default=None,
        description=(
            "Use only when the user explicitly states calendar endpoints. Values "
            "must be ISO dates or the canonical sentinel today/current_date. Never "
            "put relative, shorthand, or prose windows in start/end; use "
            "date_range_intent for those."
        ),
    )
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: str | None = Field(
        default=None,
        description="Short user-message span supporting the temporal extraction.",
    )


class _CatalogInterpretationResponse(LLMInterpretationResponse):
    """The schema owner, rather than model-authored data, marks catalog selection."""

    uses_tool_catalog: ClassVar[bool] = True


def interpretation_response_model(
    tool_catalog: ToolCatalog | None = None,
) -> type[LLMInterpretationResponse]:
    """Derive every call's argument schema from its callable declaration.

    The list remains open to zero, multiple and repeated calls. The old research
    shape fields remain readable on the compatibility model, never model-facing.
    """
    if tool_catalog is None:
        from argus.domain.capability_registry import get_tool_catalog

        tool_catalog = get_tool_catalog()
    call_models = tuple(
        _declared_call_model(declaration) for declaration in tool_catalog.declarations
    )
    if not call_models:
        call_type = ToolCall
        calls = Field(default_factory=list, max_length=0)
    else:
        call_type = (
            call_models[0]
            if len(call_models) == 1
            else Annotated[Union[call_models], Field(discriminator="tool_name")]
        )
        calls = Field(
            default_factory=list,
            max_length=MAX_TOOL_CALLS,
            description=(
                "Ordered calls to declared tools, using only facts available now. "
                "Use an empty list when no tool is needed. A tool may be called "
                "more than once with distinct call_id values. Do not force a "
                "question into one named calculation. Unknown arguments remain "
                "null only where the tool schema permits them; zero is a value."
            ),
        )
    return create_model(
        "LLMToolInterpretationResponse",
        __base__=_CatalogInterpretationResponse,
        __config__=ConfigDict(
            json_schema_extra={
                "allOf": [
                    {
                        "if": {
                            "properties": {"tool_calls": {"minItems": 1}},
                            "required": ["tool_calls"],
                        },
                        "then": {
                            "properties": {
                                "candidate_strategy_draft": {"maxProperties": 0}
                            }
                        },
                    }
                ],
            }
        ),
        intent=(CanonicalIntentName, ...),
        tool_calls=(list[call_type], calls),
        research_query=(SkipJsonSchema[None], None),
        asset_discovery=(SkipJsonSchema[None], None),
        context_question_focus=(SkipJsonSchema[None], None),
    )


def _declared_call_model(declaration: ToolDeclaration) -> type[BaseModel]:
    title = declaration.name.title().replace("_", "")
    parameters = declaration.tool_schema()["parameters"]
    arguments_type = create_model(
        f"{title}ToolArguments",
        __base__=declaration.call_arguments_type,
        __config__=ConfigDict(
            extra="forbid",
            json_schema_extra={"allOf": parameters["allOf"]}
            if "allOf" in parameters
            else {},
        ),
    )

    def validate_rules(arguments: BaseModel) -> BaseModel:
        declaration.validate_arguments(arguments)
        return arguments

    return create_model(
        f"{title}ToolCall",
        __config__=ConfigDict(extra="forbid"),
        tool_name=(Literal[declaration.name], ...),
        call_id=(str, Field(min_length=1, max_length=128)),
        arguments=(Annotated[arguments_type, AfterValidator(validate_rules)], ...),
    )
