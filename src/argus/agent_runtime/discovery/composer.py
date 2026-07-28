from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from loguru import logger

from argus.agent_runtime.discovery.contracts import (
    DISCOVERY_SIDECAR_SCHEMA_VERSION,
    ValidatedCandidate,
)
from argus.agent_runtime.discovery.extraction import extract_candidates
from argus.agent_runtime.discovery.validation import validated_candidates
from argus.agent_runtime.recovery_messages import (
    RecoveryMessageCode,
    recovery_message,
    retry_last_turn_stage_patch,
)
from argus.agent_runtime.response_language import response_language_instruction
from argus.agent_runtime.stages.interpret_types import (
    AssetDiscoveryRequest,
    InterpretDecision,
    StageResult,
)
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
    if not discovery_allowance_available:
        return await _recovery_result(
            decision=decision,
            code="discovery_limit_reached",
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
    usage: dict[str, Any] = {"search_attempted": False}
    try:
        provider = selection.search_provider_for_config(provider_id=config.provider_id)
        usage["search_attempted"] = True
        packet = provider.search(
            query,
            max_results=5,
            timeout_seconds=config.timeout_seconds,
        )
    except SearchUnavailableError as exc:
        if exc.reason == "not_configured":
            usage["search_attempted"] = False
        usage["fallback_code"] = f"search_{exc.reason}"
        logger.warning(
            "Grounded discovery search unavailable",
            reason=exc.reason,
            detail=exc.detail,
        )
        return await _recovery_result(
            decision=decision,
            code="discovery_search_failed",
            retryable=True,
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
    validated, unverified, uncorroborated = validated_candidates(
        extraction,
        packet=packet,
        resolve=resolve_asset,
        max_candidates=config.max_candidates,
        asset_class_hint=request.asset_class_hint,
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
        unverified_names=unverified,
        uncorroborated_names=uncorroborated,
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
    if retryable:
        # retryable=True must render an affordance, not just persist a flag:
        # the frontend retry rail reads metadata.retry_last_turn.
        retry_last_turn = retry_last_turn_stage_patch(current_user_message)
        if retry_last_turn is not None:
            stage_patch.update(retry_last_turn)
    if usage is not None:
        stage_patch["discovery_usage"] = usage
    return StageResult(
        outcome="ready_to_respond",
        decision=decision,
        stage_patch=stage_patch,
    )


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
        "Sources came back, but no candidate could be verified as a tradable "
        "asset, so there is nothing safe to offer."
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
                "Reply in two or three warm plain sentences that state the "
                "situation honestly, remind them their conversation and any "
                "current setup are unchanged, and invite them to name a symbol "
                "or company so you can test it. Do not list tradable asset "
                "suggestions from memory, do not mention providers or internal "
                "tools, and do not give investment advice."
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
) -> str | None:
    candidate_lines = "\n".join(
        f"- {item.symbol} ({item.name}, {item.asset_class}): {item.reason_text}"
        for item in candidates
    )
    freshness = packet.retrieved_at.date().isoformat()
    facts = [
        f"Verified candidates (the complete allowed list):\n{candidate_lines}",
        f"Sources were retrieved on {freshness} from {len(packet.results)} pages.",
    ]
    drops = _drop_reason_facts(unverified_names, uncorroborated_names)
    if drops:
        facts.append(drops.strip())
    language_instruction = response_language_instruction(language)
    messages = [
        {
            "role": "system",
            "content": (
                "You are Argus, a chat-first investing experimentation "
                f"assistant. {language_instruction} "
                "Using ONLY the verified facts below, write a short plain "
                "answer to the user's discovery request: one framing sentence, "
                "then one short line per candidate saying why it matches, and "
                "one closing sentence that these came from current sources and "
                "the user can pick one to test historically. Never add assets "
                "beyond the verified list, never rank them as best or "
                "recommend buying, never mention providers or internal tools, "
                "and keep it educational, not advice."
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
    except Exception:
        return None
    cleaned = str(response or "").strip()
    return cleaned or None


def _discovery_sidecar(
    *,
    request: AssetDiscoveryRequest,
    packet: SearchResultPacket,
    candidates: list[ValidatedCandidate],
    unverified_names: list[str],
) -> dict[str, Any]:
    query_summary = (
        request.category_description
        or ", ".join(request.anchor_symbols)
        or request.relationship
    )
    return {
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
