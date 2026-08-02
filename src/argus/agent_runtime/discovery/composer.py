from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from argus.agent_runtime.discovery.contracts import (
    DISCOVERY_SIDECAR_SCHEMA_VERSION,
    ValidatedCandidate,
)
from argus.agent_runtime.discovery.extraction import extract_candidates
from argus.agent_runtime.discovery.model_knowledge import name_candidates
from argus.agent_runtime.discovery.validation import validated_candidates
from argus.agent_runtime.recovery_messages import (
    RecoveryMessageCode,
    recovery_message,
)
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    InterpretDecision,
    StageResult,
)
from argus.agent_runtime.substage_events import emit_substage
from argus.domain.discovery_search import (
    SearchResultPacket,
    SearchUnavailableError,
    discovery_search_config,
    selection,
)
from argus.domain.market_data import resolve_asset
from argus.llm.openrouter import invoke_openrouter_chat_completion


async def discovery_stage_result_for(
    *,
    interpretation: Any,
    decision: InterpretDecision,
    state: Any,
    user: Any,
) -> StageResult | None:
    """Stage-facing wrapper: owns turn-language and allowance plumbing."""
    return await discovery_stage_result_if_applicable(
        decision=decision,
        current_user_message=state.current_user_message,
        language=(
            getattr(interpretation, "detected_user_language", None)
            or user.language_preference
        ),
        discovery_allowance_available=state.discovery_allowance_available,
    )


async def discovery_stage_result_if_applicable(
    *,
    decision: InterpretDecision,
    current_user_message: str,
    language: str,
    discovery_allowance_available: bool = True,
) -> StageResult | None:
    """Own every asset_discovery turn; other turns pass through untouched.

    The typed act is the single routing condition. Deterministic code owns the
    Search call, candidate validation, and every bound; LLM calls only extract
    from typed inputs and voice validated facts.
    """

    if decision.semantic_turn_act != "asset_discovery":
        return None
    config = discovery_search_config()
    if not config.enabled:
        return await _recovery_result(
            decision=decision,
            code="discovery_unavailable",
            retryable=False,
            current_user_message=current_user_message,
            language=language,
        )
    request = decision.asset_discovery
    query = _search_query(request)
    if request is None or not query:
        return await _recovery_result(
            decision=decision,
            code="discovery_target_missing",
            retryable=False,
            current_user_message=current_user_message,
            language=language,
        )
    # Cheap rows are the default; exhausted allowance falls through here too.
    if not request.needs_current_facts or not discovery_allowance_available:
        return await _model_knowledge_result(
            decision=decision,
            request=request,
            max_candidates=config.max_candidates,
            current_user_message=current_user_message,
            language=language,
            can_request_search=discovery_allowance_available,
        )
    usage: dict[str, Any] = {"search_attempted": False}
    try:
        provider = selection.search_provider_for_config(provider_id=config.provider_id)
        usage["search_attempted"] = True
        # Never announce a search that will not happen.
        emit_substage("discovery_search", detail=_search_subject(request))
        # Sync provider client: off the loop, or one search stalls every stream.
        packet = await asyncio.to_thread(
            provider.search,
            query,
            max_results=5,
            timeout_seconds=config.timeout_seconds,
        )
    except SearchUnavailableError as exc:
        if exc.reason == "not_configured":
            usage["search_attempted"] = False
        usage["fallback_code"] = f"search_{exc.reason}"
        permanently_unavailable = exc.reason in {
            "not_configured",
            "authentication_failed",
        }
        logger.warning(
            "Grounded discovery search unavailable",
            reason=exc.reason,
            detail=exc.detail,
        )
        return await _recovery_result(
            decision=decision,
            code=(
                "discovery_unavailable"
                if permanently_unavailable
                else "discovery_search_failed"
            ),
            retryable=not permanently_unavailable,
            current_user_message=current_user_message,
            language=language,
            usage=usage,
        )
    usage.update(
        provider_id=packet.provider_id,
        latency_ms=packet.latency_ms,
        cost_usd=packet.cost_usd,
        result_count=len(packet.results),
    )
    extraction = await extract_candidates(
        request=request, packet=packet, language=language
    )
    if extraction is None:
        usage["fallback_code"] = "extraction_unavailable"
        return await _recovery_result(
            decision=decision,
            code="discovery_search_failed",
            retryable=True,
            current_user_message=current_user_message,
            language=language,
            usage=usage,
        )
    emit_substage("discovery_verify")
    # Sync resolver lookups: off the loop, or the verify line above stalls.
    validated, unverified, uncorroborated = await asyncio.to_thread(
        lambda: validated_candidates(
            extraction,
            packet=packet,
            resolve=resolve_asset,
            max_candidates=config.max_candidates,
            asset_class_hint=request.asset_class_hint,
        )
    )
    usage.update(
        extracted_count=len(extraction.candidates),
        validated_count=len(validated),
        unverified_count=len(unverified),
        uncorroborated_count=len(uncorroborated),
    )
    if not validated:
        return await _recovery_result(
            decision=decision,
            code="discovery_no_verified_candidates",
            retryable=False,
            current_user_message=current_user_message,
            language=language,
            usage=usage,
            unverified_names=unverified,
            uncorroborated_names=uncorroborated,
        )
    voiced = await _voiced_discovery_response(
        request=request,
        candidates=validated,
        packet=packet,
        unverified_names=_user_subject_drops(
            unverified, request=request, current_user_message=current_user_message
        ),
        uncorroborated_names=_user_subject_drops(
            uncorroborated, request=request, current_user_message=current_user_message
        ),
        current_user_message=current_user_message,
        language=language,
    )
    if not voiced:
        usage["fallback_code"] = "voicing_unavailable"
        return await _recovery_result(
            decision=decision,
            code="discovery_search_failed",
            retryable=True,
            current_user_message=current_user_message,
            language=language,
            usage=usage,
        )
    sidecar = _discovery_sidecar(
        request=request,
        packet=packet,
        candidates=validated,
        unverified_names=unverified + uncorroborated,
    )
    logger.info(
        "Grounded discovery response composed",
        relationship=request.relationship,
        result_count=len(packet.results),
        extracted_count=len(extraction.candidates),
        validated_count=len(validated),
        unverified_count=len(unverified),
        uncorroborated_count=len(uncorroborated),
        search_latency_ms=packet.latency_ms,
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={
            "assistant_response": voiced,
            "discovery": sidecar,
            "discovery_usage": usage,
        },
    )


async def _model_knowledge_result(
    *,
    decision: InterpretDecision,
    request: AssetDiscoveryRequest,
    max_candidates: int,
    current_user_message: str,
    language: str,
    can_request_search: bool,
) -> StageResult:
    """Model knowledge in, resolver-verified rows out; zero sources in the
    sidecar is the ungrounded marker (derived, never asserted)."""
    extraction = await name_candidates(request=request, language=language)
    if extraction is None:
        return await _recovery_result(
            decision=decision,
            code="discovery_suggestions_unavailable",
            retryable=True,
            current_user_message=current_user_message,
            language=language,
        )
    packet = _model_knowledge_packet()
    validated, unverified, uncorroborated = validated_candidates(
        extraction,
        packet=packet,
        resolve=resolve_asset,
        max_candidates=max_candidates,
        asset_class_hint=request.asset_class_hint,
        require_source_evidence=False,
    )
    if not validated:
        return await _recovery_result(
            decision=decision,
            code="discovery_no_verified_candidates",
            retryable=False,
            current_user_message=current_user_message,
            language=language,
            unverified_names=unverified,
            uncorroborated_names=uncorroborated,
        )
    voiced = await _voiced_discovery_response(
        request=request,
        candidates=validated,
        packet=packet,
        unverified_names=_user_subject_drops(
            unverified, request=request, current_user_message=current_user_message
        ),
        uncorroborated_names=_user_subject_drops(
            uncorroborated, request=request, current_user_message=current_user_message
        ),
        current_user_message=current_user_message,
        language=language,
        grounded=False,
    )
    if not voiced:
        return await _recovery_result(
            decision=decision,
            code="discovery_suggestions_unavailable",
            retryable=True,
            current_user_message=current_user_message,
            language=language,
        )
    sidecar = _discovery_sidecar(
        request=request,
        packet=packet,
        candidates=validated,
        unverified_names=unverified + uncorroborated,
        can_request_search=can_request_search,
    )
    logger.info(
        "Model-knowledge discovery response composed",
        relationship=request.relationship,
        extracted_count=len(extraction.candidates),
        validated_count=len(validated),
        unverified_count=len(unverified),
        uncorroborated_count=len(uncorroborated),
        can_request_search=can_request_search,
    )
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch={"assistant_response": voiced, "discovery": sidecar},
    )


def _model_knowledge_packet() -> SearchResultPacket:
    return SearchResultPacket(
        results=(),
        retrieved_at=datetime.now(timezone.utc),
        latency_ms=0,
        provider_id="model_knowledge",
    )


def _search_subject(request: AssetDiscoveryRequest) -> str | None:
    """Human subject for progress display: the typed interpretation's own
    words in the turn language, never the machine query string."""
    category = (request.category_description or "").strip()
    if category:
        return category
    anchors = ", ".join(
        symbol.strip().upper() for symbol in request.anchor_symbols if symbol.strip()
    )
    return anchors or None


def _search_query(request: AssetDiscoveryRequest | None) -> str | None:
    """Deterministic machine query for the Search provider; never user prose."""
    if request is None:
        return None
    anchors = ", ".join(
        symbol.strip().upper() for symbol in request.anchor_symbols if symbol.strip()
    )
    category = (request.category_description or "").strip()
    universe = {
        "crypto": "tradable cryptocurrencies",
        "currency_pair": "tradable currency pairs",
    }.get(request.asset_class_hint or "", "publicly traded companies")
    if request.relationship == "category":
        if not category:
            return None
        return f"{universe}: {category}"
    if not anchors and not category:
        return None
    subject = anchors or category
    if request.relationship == "peer":
        return f"{universe} similar to {subject}"
    return f"{universe} comparable to {subject} for performance comparison"


async def _recovery_result(
    *,
    decision: InterpretDecision,
    code: RecoveryMessageCode,
    retryable: bool,
    current_user_message: str,
    language: str,
    usage: dict[str, Any] | None = None,
    unverified_names: list[str] | None = None,
    uncorroborated_names: list[str] | None = None,
) -> StageResult:
    voiced = await _voiced_discovery_recovery(
        code=code,
        current_user_message=current_user_message,
        language=language,
        unverified_names=unverified_names or [],
        uncorroborated_names=uncorroborated_names or [],
    )
    # The typed recovery object persists in both branches so codes such as a
    # retryable discovery_search_failed survive into metadata and analytics.
    # prompt_source=llm_generated tells clients the voiced prose owns display;
    # without it (deterministic fallback), clients render localized copy from
    # the code.
    assistant_response = voiced or recovery_message(code, retryable=retryable)
    stage_patch: dict[str, Any] = {"assistant_response": assistant_response}
    if voiced:
        stage_patch["recovery"] = {
            "code": code,
            "retryable": retryable,
            "prompt_source": "llm_generated",
        }
    # retryable=True is the whole signal; the API layer owns the durable retry.
    if usage is not None:
        stage_patch["discovery_usage"] = usage
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=stage_patch,
    )


def _user_subject_drops(
    names: list[str],
    *,
    request: AssetDiscoveryRequest,
    current_user_message: str,
) -> list[str]:
    """Presentation gate: a dropped name is mentioned only when it is the
    user's own subject (typed anchor, or named in their message). Internal
    filtering stays silent; telemetry keeps the full lists."""
    if not names:
        return []
    haystack = _alnum(current_user_message)
    anchors = {_alnum(symbol) for symbol in request.anchor_symbols}
    kept: list[str] = []
    for name in names:
        whole = _alnum(name)
        first = _alnum(name.split()[0]) if name.split() else ""
        if (
            (whole and whole in haystack)
            or (len(first) >= 3 and first in haystack)
            or whole in anchors
            or first in anchors
        ):
            kept.append(name)
    return kept


def _alnum(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def _drop_reason_facts(
    unverified_names: list[str],
    uncorroborated_names: list[str],
) -> str:
    """State the true reason a name was dropped, not a convenient one.

    "Not verifiable as tradable" is false for an asset that resolves fine but
    does not correspond to what the sources named -- a Bitcoin trust is plainly
    tradable. Conflating the two would have Argus explain a correct decision
    with a wrong reason.
    """
    facts = ""
    if unverified_names:
        facts += (
            " Names seen in sources but not verifiable as tradable: "
            + ", ".join(unverified_names)
            + ". You may mention them only as unverified."
        )
    if uncorroborated_names:
        facts += (
            " Names seen in sources that resolve to a real listing, but not one"
            " you could confirm is the asset the user meant: "
            + ", ".join(uncorroborated_names)
            + ". Say only that you could not confirm the match; never say they"
            " are untradable."
        )
    return facts


_RECOVERY_VOICING_FACTS: dict[str, str] = {
    "discovery_unavailable": (
        "Grounded source-backed discovery is not available right now, so you "
        "cannot look up current candidates and you will not guess from memory."
    ),
    "discovery_search_failed": (
        "The source-backed lookup failed temporarily. You will not guess names "
        "from memory. The user can simply ask again in a moment."
    ),
    "discovery_no_verified_candidates": (
        "No candidate could be verified as a tradable asset, so there is "
        "nothing safe to offer."
    ),
    "discovery_suggestions_unavailable": (
        "Putting together suggestions failed temporarily. You will not guess "
        "names inline. The user can simply ask again in a moment."
    ),
    "discovery_limit_reached": (
        "The user has used all grounded lookups available for now; the "
        "allowance resets on a schedule."
    ),
    "discovery_target_missing": (
        "The request did not name a category or an anchor company, so there is "
        "nothing concrete to search for yet."
    ),
}


async def _voiced_discovery_recovery(
    *,
    code: RecoveryMessageCode,
    current_user_message: str,
    language: str,
    unverified_names: list[str],
    uncorroborated_names: list[str] | None = None,
) -> str | None:
    message = current_user_message.strip()
    facts = _RECOVERY_VOICING_FACTS.get(code)
    if not message or facts is None:
        return None
    facts += _drop_reason_facts(unverified_names, uncorroborated_names or [])
    language_instruction = response_language_instruction(language)
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation "
                "assistant. The user asked you to find or discover assets. "
                f"Situation: {facts} {language_instruction} "
                "Reply in at most two short plain sentences: state the "
                "situation honestly, then one concrete next step (retry, or "
                "name a symbol to test). No reassurance boilerplate, no "
                "tradable asset suggestions from memory, no providers or "
                "internal tools, no investment advice."
            ),
        },
        {"role": "user", "content": message},
    ]
    try:
        response = await invoke_openrouter_chat_completion(
            task="chat_composer",
            messages=messages,
        )
    except Exception:
        return None
    cleaned = str(response or "").strip()
    return cleaned or None


async def _voiced_discovery_response(
    *,
    request: AssetDiscoveryRequest,
    candidates: list[ValidatedCandidate],
    packet: SearchResultPacket,
    unverified_names: list[str],
    uncorroborated_names: list[str],
    current_user_message: str,
    language: str,
    grounded: bool = True,
) -> str | None:
    candidate_lines = "\n".join(
        f"- {item.symbol} ({item.name}, {item.asset_class}): {item.reason_text}"
        for item in candidates
    )
    facts = [f"Verified candidates (the complete allowed list):\n{candidate_lines}"]
    if grounded:
        freshness = packet.retrieved_at.date().isoformat()
        facts.append(
            f"Sources were retrieved on {freshness} from {len(packet.results)} pages."
        )
    else:
        facts.append(
            "These candidates come from your general knowledge. No search was "
            "performed and there are no sources."
        )
    drops = _drop_reason_facts(unverified_names, uncorroborated_names)
    if drops:
        facts.append(drops.strip())
    language_instruction = response_language_instruction(language)
    # Rows and the marker line own candidates and grounding; prose must not
    # duplicate the screen.
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation "
                f"assistant. {language_instruction} "
                "The interface below your reply already shows every verified "
                "candidate as a tappable row and already states whether the "
                "answer came from current sources or general knowledge. Write "
                "ONE short framing sentence answering the user's discovery "
                "request; add one brief sentence about the dropped names only "
                "if the facts mention any. Do not list or name the candidates, "
                "do not restate where the answer came from, never add assets "
                "beyond the verified list, never rank or recommend buying, "
                "never mention providers or internal tools."
            ),
        },
        {"role": "system", "content": "\n\n".join(facts)},
        {"role": "user", "content": current_user_message.strip()},
    ]
    try:
        response = await invoke_openrouter_chat_completion(
            task="discovery_voicing",
            messages=messages,
        )
    except Exception as exc:
        # Unlogged, a dead voicing model looks like a transient blip.
        logger.warning(
            "Discovery voicing call failed",
            error=str(exc),
            grounded=grounded,
            failure_classification="discovery_voicing_unavailable",
        )
        return None
    cleaned = str(response or "").strip()
    return cleaned or None


def _discovery_sidecar(
    *,
    request: AssetDiscoveryRequest,
    packet: SearchResultPacket,
    candidates: list[ValidatedCandidate],
    unverified_names: list[str],
    can_request_search: bool | None = None,
) -> dict[str, Any]:
    query_summary = (
        request.category_description
        or ", ".join(request.anchor_symbols)
        or request.relationship
    )
    # Backend-owned: the escalation row renders only while this is true.
    escalation = (
        {"can_request_search": can_request_search}
        if can_request_search is not None
        else {}
    )
    return {
        **escalation,
        "schema_version": DISCOVERY_SIDECAR_SCHEMA_VERSION,
        "kind": "asset_discovery",
        "relationship": request.relationship,
        "query_summary": str(query_summary)[:200],
        "retrieved_at": packet.retrieved_at.isoformat(),
        "sources": [
            {
                "title": result.title,
                "domain": urlparse(result.url).netloc,
                "url": result.url,
                "source_date": result.source_date,
            }
            for result in packet.results
        ],
        "candidates": [
            {
                "symbol": item.symbol,
                "name": item.name,
                "asset_class": item.asset_class,
                "reason_text": item.reason_text,
                "source_indices": list(item.source_indices),
            }
            for item in candidates
        ],
        "unverified_names": list(unverified_names),
    }
