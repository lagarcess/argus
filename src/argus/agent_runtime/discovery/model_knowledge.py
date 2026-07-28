from __future__ import annotations

from loguru import logger

from argus.agent_runtime.discovery.contracts import DiscoveryExtraction
from argus.agent_runtime.stages.interpret_types import AssetDiscoveryRequest
from argus.llm.openrouter import invoke_openrouter_json_schema


async def name_candidates(
    *,
    request: AssetDiscoveryRequest,
    language: str,
) -> DiscoveryExtraction | None:
    """Name candidates from model knowledge; the resolver still owns truth.

    Same deterministic spine as the grounded path: the LLM only proposes
    names from the typed request, and every name must pass resolve_asset()
    before it can render. What this path cannot offer is currency -- the
    caller marks the output as unsourced.
    """
    target = _target_description(request)
    messages = [
        {
            "role": "system",
            "content": (
                "You suggest candidate tradable assets for an investing "
                "sandbox from your own general knowledge. No web search is "
                "available. List up to 8 distinct real, currently listed, "
                "widely known publicly tradable assets that genuinely match "
                "the request. For each: the plain company/asset name, your "
                "best ticker symbol guess, and one short factual reason "
                f"written in the user's language ({language}). Leave "
                "source_indices empty; there are no sources. Never invent "
                "tickers, never include private or delisted companies, and "
                "omit anything you are unsure is still listed. If nothing "
                "matches, return an empty list."
            ),
        },
        {"role": "user", "content": f"Request: {target}"},
    ]
    # A raise here would escape the discovery stage into generic runtime
    # failure; the composer maps None to a typed retryable recovery instead.
    try:
        return await invoke_openrouter_json_schema(
            task="discovery_model_knowledge",
            messages=messages,
            schema_model=DiscoveryExtraction,
            schema_name="discovery_model_knowledge",
        )
    except Exception as exc:
        logger.warning(
            "Discovery model-knowledge call failed",
            error=str(exc),
            failure_classification="discovery_suggestions_unavailable",
        )
        return None


def _target_description(request: AssetDiscoveryRequest) -> str:
    anchors = ", ".join(request.anchor_symbols)
    if request.relationship == "category":
        base = request.category_description or "the described category"
        return f"publicly tradable assets in this category: {base}"
    relation = (
        "peers or close competitors of"
        if request.relationship == "peer"
        else "comparable assets to compare against"
    )
    subject = anchors or request.category_description or "the named asset"
    return f"publicly tradable {relation} {subject}"
