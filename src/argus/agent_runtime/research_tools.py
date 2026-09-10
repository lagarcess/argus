"""Typed research operations for the shared executable tool catalog.

Calls select operations, never question categories. Existing retrieval and
asset-discovery services remain the owners of provider work, sources, cache,
quota admission, and background completion.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Annotated, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from argus.agent_runtime import research_grounded as grounded
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRelationship,
    AssetDiscoveryRequest,
    StageResult,
    StructuredInterpretation,
)
from argus.agent_runtime.state.models import RunState, UserState
from argus.domain.research.config import research_rail_enabled
from argus.domain.research.contracts import (
    QuestionShape,
    ResearchNamePair,
    ResearchSource,
    RetrievedRow,
)

if TYPE_CHECKING:
    from argus.domain.tool_contracts import (
        ToolCardPresentation,
        ToolFailureStatus,
        ToolOutcome,
    )
    from argus.domain.tool_declaration import ToolDeclaration


class ResearchExecutionContext(Protocol):
    """Request-scoped identity and publication, injected by the runtime."""

    state: RunState
    user: UserState | None
    stage_result: StageResult | None


class ResearchArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)

    request: str = Field(min_length=1, max_length=2000)


class ResearchPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    description: str = Field(min_length=1, max_length=250)
    start_date: date | None = None
    closed_window: bool = False


class FastQuoteArguments(ResearchArguments):
    """Current equity or ETF market-data figures, with no causal narrative."""

    symbols: list[str] = Field(min_length=1, max_length=5)


class BalancedLookupArguments(ResearchArguments):
    """Sourced public facts and figures under the existing retrieval policy."""

    symbols: list[str] = Field(default_factory=list, max_length=5)
    period: ResearchPeriod | None = None


class ThoroughResearchArguments(BalancedLookupArguments):
    """A deeper sourced read whose completion uses the existing background job."""


class ScreeningArguments(ResearchArguments):
    """Retrieve assets and the figures proving each explicit condition."""

    criteria: list[str] = Field(min_length=1, max_length=12)
    universe: str | None = Field(default=None, max_length=250)
    period: ResearchPeriod | None = None


class PeerExpansionArguments(AssetDiscoveryRequest, ResearchArguments):
    """Find resolver-verified candidate assets around anchors or a category."""

    @model_validator(mode="after")
    def _has_subject(self) -> PeerExpansionArguments:
        if (
            not any(symbol.strip() for symbol in self.anchor_symbols)
            and not self.category_description
        ):
            raise ValueError("peer expansion needs an anchor or category")
        return self


class ResearchToolResult(BaseModel):
    """Read-compatible research envelope; callable returns narrow its fact boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["completed", "pending"] = "completed"
    answer: str | None = None
    rows: tuple[RetrievedRow, ...] = ()
    sources: tuple[ResearchSource, ...] = ()
    retrieved_at: str | None = None
    relationship: AssetDiscoveryRelationship | None = None
    subjects: tuple[ResearchNamePair, ...] = ()
    peers: tuple[ResearchNamePair, ...] = ()

    @model_validator(mode="after")
    def _pending_has_no_answer(self) -> ResearchToolResult:
        if self.status == "pending" and (
            self.answer is not None
            or self.rows
            or self.sources
            or self.subjects
            or self.peers
            or self.relationship is not None
        ):
            raise ValueError("Pending research cannot carry completed facts")
        return self


class ResearchFiguresResult(ResearchToolResult):
    """A published nonblank answer with any typed figures the provider supplied.

    Figures retain their units, dates, and authored citations. A figure
    without a citation stays in the answer with the publisher's source
    limitation. Public citations may be absent for market-data answers.
    """

    status: Literal["completed"] = "completed"
    answer: str = Field(min_length=1, pattern=r"\S")
    rows: tuple[RetrievedRow, ...] = ()
    relationship: None = None


class CitedResearchFiguresResult(ResearchFiguresResult):
    """A published answer with retained public sources and optional typed figures.

    The shared publication policy requires these sources. Their presence
    does not establish that every figure cites a retrieved page.
    """

    sources: tuple[ResearchSource, ...] = Field(min_length=1)


class ResearchCandidatesResult(ResearchToolResult):
    """Completed resolver-verified candidate assets for the requested selection purpose.

    Sources accompany current retrieval; a model-knowledge candidate list has
    no citations. This result carries candidate identities, not numeric figures.
    """

    status: Literal["completed"] = "completed"
    rows: tuple[()] = ()
    relationship: AssetDiscoveryRelationship
    peers: tuple[ResearchNamePair, ...] = Field(min_length=1)


class ResearchPendingResult(ResearchToolResult):
    """An admitted research job receipt with no completed evidence or answer."""

    status: Literal["pending"] = "pending"
    answer: None = None
    rows: tuple[()] = ()
    sources: tuple[()] = ()
    relationship: None = None
    subjects: tuple[()] = ()
    peers: tuple[()] = ()


class ResearchWorkflowResult(
    RootModel[
        Annotated[
            CitedResearchFiguresResult | ResearchPendingResult,
            Field(discriminator="status"),
        ]
    ]
):
    """A pending job receipt or completed published answer, distinguished by status."""

    model_config = ConfigDict(frozen=True)


async def fast_quote(
    arguments: FastQuoteArguments, *, context: ResearchExecutionContext
) -> ResearchFiguresResult:
    result = await _read(
        arguments,
        query=ResearchQueryExtraction(
            question_kind="live_quote",
            symbols=arguments.symbols,
        ),
        shape="fast",
        context=context,
    )
    return ResearchFiguresResult.model_validate(result.model_dump())


async def balanced_lookup(
    arguments: BalancedLookupArguments, *, context: ResearchExecutionContext
) -> CitedResearchFiguresResult:
    result = await _read(
        arguments,
        query=_sourced_query(arguments),
        shape="balanced",
        context=context,
    )
    return CitedResearchFiguresResult.model_validate(result.model_dump())


async def thorough_research(
    arguments: ThoroughResearchArguments, *, context: ResearchExecutionContext
) -> ResearchWorkflowResult:
    result = await _read(
        arguments,
        query=_sourced_query(arguments),
        shape="thorough",
        context=context,
    )
    return ResearchWorkflowResult.model_validate(result.model_dump())


async def screening(
    arguments: ScreeningArguments, *, context: ResearchExecutionContext
) -> CitedResearchFiguresResult:
    result = await _read(
        arguments,
        query=ResearchQueryExtraction(
            question_kind="screening",
            screening_criteria=arguments.criteria,
            sector_of_interest=arguments.universe,
            requires_publisher_sources=True,
            **_period_facts(arguments.period),
        ),
        shape="balanced",
        context=context,
    )
    return CitedResearchFiguresResult.model_validate(result.model_dump())


async def peer_expansion(
    arguments: PeerExpansionArguments, *, context: ResearchExecutionContext
) -> ResearchCandidatesResult:
    from argus.agent_runtime.research_find import find_assets_stage_result

    user, state, interpretation = _call_context(arguments, context)
    request = AssetDiscoveryRequest.model_validate(
        arguments.model_dump(include=set(AssetDiscoveryRequest.model_fields))
    )
    result = await find_assets_stage_result(
        request=request,
        interpretation=interpretation,
        decision=None,
        state=state,
        user=user,
    )
    published = _published_result(result, context=context)
    return ResearchCandidatesResult.model_validate(published.model_dump())


def _period_facts(period: ResearchPeriod | None) -> dict[str, Any]:
    return {
        "period_of_interest": period.description if period is not None else None,
        "period_start_date": period.start_date if period is not None else None,
        "period_is_closed_window": period.closed_window if period is not None else False,
    }


def _sourced_query(
    arguments: BalancedLookupArguments,
) -> ResearchQueryExtraction:
    # The selected callable already owns the operation. This is the existing
    # service's public-facts mode, not a fresh classification of the request.
    return ResearchQueryExtraction(
        question_kind="current_external",
        symbols=arguments.symbols,
        requires_publisher_sources=True,
        **_period_facts(arguments.period),
    )


def _call_context(
    arguments: ResearchArguments, context: ResearchExecutionContext
) -> tuple[UserState, RunState, StructuredInterpretation]:
    from argus.domain.tool_declaration import ToolInvocationError

    context.stage_result = None
    if not research_rail_enabled():
        raise ToolInvocationError("unavailable", code="research_disabled")
    if context.user is None:
        raise ToolInvocationError("unavailable", code="research_context_missing")
    # The requested call owns what is retrieved and cached. The full turn may
    # contain private context or several independent requests, none of which
    # may silently replace this call's declared arguments.
    state = context.state.model_copy(update={"current_user_message": arguments.request})
    interpretation = StructuredInterpretation(
        intent="conversation_followup",
        task_relation="continue",
        user_goal_summary=arguments.request,
        semantic_turn_act="educational_question",
    )
    return context.user, state, interpretation


async def _read(
    arguments: ResearchArguments,
    *,
    query: ResearchQueryExtraction,
    shape: QuestionShape,
    context: ResearchExecutionContext,
) -> ResearchToolResult:
    from argus.agent_runtime.research_answer import _resolved_subjects
    from argus.domain.tool_declaration import ToolInvocationError

    user, state, interpretation = _call_context(arguments, context)
    subjects = _resolved_subjects(query)
    if query.symbols and len(subjects) != len(set(s.upper() for s in query.symbols)):
        raise ToolInvocationError(
            "invalid", code="research_subject_unresolved", fields=("symbols",)
        )
    if any(subject["asset_class"] != "equity" for subject in subjects):
        result = await grounded.off_coverage_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            state=state,
            user=user,
        )
    elif shape == "thorough":
        result = grounded.thorough_job_result(
            query=query,
            subjects=subjects,
            interpretation=interpretation,
            user=user,
            message=arguments.request,
        )
    else:
        result = await grounded.grounded_result(
            query=query,
            subjects=subjects,
            shape=shape,
            interpretation=interpretation,
            state=state,
            user=user,
        )
    return _published_result(result, context=context)


def _published_result(
    result: StageResult | None, *, context: ResearchExecutionContext
) -> ResearchToolResult:
    from argus.domain.tool_declaration import ToolInvocationError

    context.stage_result = result
    if result is None:
        raise ToolInvocationError("unavailable", code="research_result_unavailable")
    return research_result_from_patch(result.stage_patch)


def research_result_from_patch(patch: dict[str, Any]) -> ResearchToolResult:
    """Project inline and background completion through the same typed return."""
    from argus.domain.tool_declaration import ToolInvocationError

    recovery = patch.get("recovery") or {}
    if recovery.get("code"):
        # Recovery owns the no-answer state even when no provider attempt
        # produced usage or a degraded research sidecar.
        raise ToolInvocationError("unavailable", code=recovery["code"])
    if "research_job_request" in patch:
        return ResearchToolResult(status="pending")
    sidecar = patch.get("research") or {}
    degraded = sidecar.get("degraded") or {}
    code = degraded.get("code")
    if code:
        status: ToolFailureStatus = (
            "unavailable"
            if code.startswith("research_unavailable")
            or code
            in {
                "research_capacity_exhausted",
                "research_not_grounded",
                "survey_not_grounded",
            }
            else "bounded"
        )
        raise ToolInvocationError(status, code=code)
    follow_up = sidecar.get("follow_up") or {}
    # Find results have a richer discovery source list, which remains its
    # only persisted owner. This is the typed result projection of that list.
    discovery = patch.get("discovery") or {}
    sources = discovery.get("sources", []) if discovery else sidecar.get("sources", [])
    return ResearchToolResult(
        answer=patch.get("assistant_response"),
        rows=tuple(RetrievedRow.model_validate(row) for row in sidecar.get("rows", [])),
        sources=tuple(ResearchSource.model_validate(source) for source in sources),
        retrieved_at=sidecar.get("retrieved_at"),
        relationship=discovery.get("relationship"),
        subjects=tuple(
            ResearchNamePair.model_validate(item)
            for item in follow_up.get("subjects", [])
        ),
        peers=tuple(
            ResearchNamePair.model_validate(item) for item in sidecar.get("peers", [])
        ),
    )


def research_outcome_from_patch(patch: dict[str, Any]) -> ToolOutcome:
    """Preserve typed provider failures when a background job completes."""
    from argus.domain.tool_contracts import ToolOutcome
    from argus.domain.tool_declaration import ToolInvocationError

    try:
        result = research_result_from_patch(patch)
    except ToolInvocationError as exc:
        return exc.outcome
    return ToolOutcome(status="succeeded", result=result.model_dump(mode="json"))


def research_card_presentation(
    arguments: ResearchArguments, outcome: ToolOutcome
) -> ToolCardPresentation:
    """Card facts come from the same typed rows the research sidecar publishes."""
    from argus.domain.tool_contracts import (
        LocalizedText,
        ToolCardPresentation,
        ToolFact,
        ToolInputFact,
    )

    inputs = [
        ToolInputFact(
            name="request",
            label=LocalizedText(locale_key="chat.tools.research.request"),
            value=arguments.request,
        )
    ]
    if outcome.status != "succeeded":
        return ToolCardPresentation(
            title=LocalizedText(locale_key="chat.tools.failed"),
            inputs=inputs,
            notes=[LocalizedText(locale_key="chat.tools.research.unavailable")],
        )
    result = ResearchToolResult.model_validate(outcome.result)
    facts = [
        ToolFact(
            name=f"figure_{index}",
            label=LocalizedText(
                locale_key="chat.tools.research.figure",
                interpolation_args={"subject": row.subject, "label": row.label},
            ),
            value=row.value,
            unit=LocalizedText(
                locale_key="chat.tools.research.unit",
                interpolation_args={"unit": row.unit},
            ),
        )
        for index, row in enumerate(result.rows)
    ]
    if not facts:
        facts = [
            ToolFact(
                name=f"subject_{index}",
                label=LocalizedText(
                    locale_key="chat.tools.research.subject",
                    interpolation_args={"name": item.name},
                ),
                value=item.symbol,
            )
            for index, item in enumerate((*result.subjects, *result.peers))
        ]
    return ToolCardPresentation(
        title=LocalizedText(locale_key="chat.tools.research.title"),
        answer=facts[0] if facts else None,
        rows=facts[1:],
        narrative=result.answer,
        sources=list(result.sources),
        inputs=inputs,
        notes=[LocalizedText(locale_key="chat.tools.research.pending")]
        if result.status == "pending"
        else [],
    )


def get_research_declarations() -> tuple[ToolDeclaration, ...]:
    """The five existing operations declared in the shared tool catalog."""
    from argus.domain.tool_declaration import (
        ToolCardBinding,
        ToolDeclaration,
        ToolPolicy,
        ToolProgressTemplate,
    )

    binding = ToolCardBinding(
        card_type="research",
        version=1,
        presenter=research_card_presentation,
    )
    domain = (
        "Research values never become simulation inputs; market data is re-grounded before a test.",
        "Unresolved requested subjects are invalid. The shared publisher policy owns answer availability; unverified asset identities cannot become test actions.",
        "The shared research cache, quota admission, provider pricing, and public-source filters remain authoritative.",
    )
    return (
        ToolDeclaration(
            name="fast_quote",
            description="Retrieve current market-data figures for named equity or ETF symbols. Does not explain causes or narratives.",
            handler=fast_quote,
            policy=ToolPolicy(
                execution="provider", external_calls=1, confirmation="never"
            ),
            progress=ToolProgressTemplate("chat.tools.progress.fast_quote", ("symbols",)),
            card=binding,
            domain=domain,
        ),
        ToolDeclaration(
            name="balanced_lookup",
            description="Retrieve cited facts and figures from public sources for named subjects and a requested time period. The shared retrieval service owns freshness.",
            handler=balanced_lookup,
            policy=ToolPolicy(
                execution="provider",
                external_calls=2,
                confirmation="never",
                public_receipt="cited_facts",
            ),
            progress=ToolProgressTemplate(
                "chat.tools.progress.balanced_lookup", ("request",)
            ),
            card=binding,
            domain=domain,
        ),
        ToolDeclaration(
            name="thorough_research",
            description="Research a deeper source-backed comparison or analysis. Uses an existing background job and returns a pending receipt until it completes.",
            handler=thorough_research,
            policy=ToolPolicy(
                execution="workflow",
                external_calls=1,
                confirmation="never",
                public_receipt="cited_facts",
            ),
            progress=ToolProgressTemplate(
                "chat.tools.progress.thorough_research", ("request",)
            ),
            card=binding,
            domain=domain,
        ),
        ToolDeclaration(
            name="screening",
            description="Retrieve candidate assets and the cited figures that establish whether every explicit condition holds.",
            handler=screening,
            policy=ToolPolicy(
                execution="provider",
                external_calls=3,
                confirmation="never",
                public_receipt="cited_facts",
            ),
            progress=ToolProgressTemplate("chat.tools.progress.screening", ("request",)),
            card=binding,
            domain=domain,
        ),
        ToolDeclaration(
            name="peer_expansion",
            description="Find resolver-verified candidate assets related to named anchors or a category, using current sources when requested.",
            handler=peer_expansion,
            policy=ToolPolicy(
                execution="provider", external_calls=1, confirmation="never"
            ),
            progress=ToolProgressTemplate(
                "chat.tools.progress.peer_expansion", ("request",)
            ),
            card=binding,
            domain=domain,
        ),
    )
