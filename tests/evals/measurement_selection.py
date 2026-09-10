"""Collective delivered selection evidence, independent of operation names."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from argus.agent_runtime.asset_identity import asset_label_parts
from argus.agent_runtime.discovery.contracts import ValidatedCandidate
from argus.agent_runtime.discovery.validation import resolution_matches_named_asset
from argus.agent_runtime.research_tools import ResearchToolResult
from argus.domain.market_data.assets import ResolvedAsset
from argus.domain.research.contracts import ResearchSource
from argus.domain.research.evidence_policy import ResearchEvidencePolicy
from argus.domain.tool_contracts import ToolCall, ToolOutcome, ToolResultCard
from argus.domain.tool_declaration import _validate_return
from pydantic import TypeAdapter, ValidationError

SELECTION_CONTRACT_VERSION = "argus-selection-evidence/v2"
SELECTION_RELEVANCE = "selection_relevance"
SELECTION_RUBRIC = f"""
Selection contract: {SELECTION_CONTRACT_VERSION}
Additional requested criterion, selection_relevance: assess whether the delivered
answer and selectable assets address the unchanged selection_expectations and
the user's request. Preserve the requested category, relationship, and named
anchors, including whether the user requested peers or a comparison. Judge the
facts against the requested period or currentness; retrieval age alone does
not establish that a figure is current. A model citation outside the retrieved
drawer is retained as such, not described as a fetched page. Judge the
collective delivery: any valid combination of operations may supply the answer.
No operation name or input form is required. Input requests are not results.
selection_evidence contains retained delivered facts, not additional user-visible
content. Structural identity, class, citations, freshness, completion, and action
binding are checked separately; a relevance pass cannot override those failures.
Missing evidence is not permission to assume the requested meaning was delivered.
"""


def is_selection_evidence(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("contract_version") == SELECTION_CONTRACT_VERSION
    )


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _asset(raw: Any) -> dict[str, str] | None:
    raw = _dict(raw)
    try:
        resolved = TypeAdapter(ResolvedAsset).validate_python(
            {
                "canonical_symbol": raw["symbol"],
                "raw_symbol": raw["symbol"],
                "name": raw["name"],
                "asset_class": raw["asset_class"],
            }
        )
    except (KeyError, ValidationError, TypeError):
        return None
    return {
        "symbol": resolved.canonical_symbol,
        "name": resolved.name,
        "asset_class": resolved.asset_class,
    }


def _same_entity(asset: dict, *, name: str, symbol: str) -> bool:
    if symbol.upper() != asset["symbol"].upper():
        return False
    return resolution_matches_named_asset(
        display_name=name,
        symbol_guess=symbol,
        resolved=ResolvedAsset(
            canonical_symbol=asset["symbol"],
            raw_symbol=asset["symbol"],
            name=asset["name"],
            asset_class=asset["asset_class"],
        ),
        asset_class=asset["asset_class"],
        asset_class_hint=None,
    )


def completed_research_deliveries(
    calls: list[dict], patch: dict
) -> list[tuple[ToolResultCard, ResearchToolResult, dict]]:
    from argus.domain.capability_registry import get_tool_catalog

    deliveries = []
    for raw_call in calls:
        try:
            call = ToolCall.model_validate(raw_call)
        except (ValidationError, TypeError):
            continue
        declaration = get_tool_catalog().get(call.tool_name)
        if declaration is None:
            continue
        try:
            arguments = declaration.validate_arguments(call.arguments).model_dump(
                mode="json"
            )
        except (ValueError, TypeError):
            continue
        records = [
            record
            for record in patch.get("tool_call_records", [])
            if record.get("call_id") == call.call_id
        ]
        if (
            len(records) != 1
            or records[0].get("tool_name") != call.tool_name
            or records[0].get("outcome") != "succeeded"
        ):
            continue
        try:
            returned = ToolOutcome.model_validate(records[0].get("tool_outcome"))
        except (ValidationError, TypeError):
            continue
        for raw_card in _dict(patch.get("final_response_payload")).get(
            "tool_result_cards", []
        ):
            try:
                card = ToolResultCard.model_validate(raw_card)
                declared_result = _validate_return(
                    declaration.result_type, card.outcome.result
                )
                result = ResearchToolResult.model_validate(
                    declared_result.model_dump(mode="json")
                )
            except (ValueError, TypeError):
                continue
            if (
                (card.call_id, card.tool_name, card.arguments)
                != (call.call_id, call.tool_name, arguments)
                or (card.card_type, card.card_version)
                != (declaration.card.card_type, declaration.card.version)
                or card.outcome != returned
                or card.outcome.status != "succeeded"
                or result.status != "completed"
                or not (
                    card.presentation.answer is not None
                    or (card.presentation.narrative or "").strip()
                )
            ):
                continue
            effects = [
                effect
                for effect in patch.get("tool_effects", [])
                if (
                    effect.get("call_id"),
                    effect.get("tool_name"),
                    effect.get("artifact_id"),
                )
                == (card.call_id, card.tool_name, card.artifact_id)
            ]
            if len(effects) == 1:
                deliveries.append((card, result, _dict(effects[0].get("stage_patch"))))
    return deliveries


def observe_selection(
    *, calls: list[dict], patch: dict, final_patch: dict
) -> dict[str, Any]:
    """Read existing publication owners; neither question nor call arguments supply facts."""
    deliveries = completed_research_deliveries(calls, patch)
    owners: list[dict] = []
    facts: list[dict] = []
    for card, result, effect in deliveries:
        provenance = {
            "retrieved_at": result.retrieved_at,
            "evidence_policy": result.evidence_policy.model_dump(mode="json")
            if result.evidence_policy is not None
            else None,
        }
        result_assets = {
            (item.symbol, item.name) for item in (*result.subjects, *result.peers)
        }
        discovery = _dict(effect.get("discovery"))
        sources = {
            source.url: source.model_dump(mode="json")
            for source in card.presentation.sources
            if source in result.sources
        }
        for raw_candidate in discovery.get("candidates", []):
            try:
                candidate = ValidatedCandidate.model_validate(raw_candidate)
            except (ValidationError, TypeError):
                continue
            if (candidate.symbol, candidate.name) not in result_assets:
                continue
            asset = _asset(candidate.model_dump())
            if asset is not None:
                owners.append(asset)
                linked = discovery.get("sources", [])
                candidate_sources = []
                for index in candidate.source_indices:
                    source = _dict(linked[index]) if 0 <= index < len(linked) else {}
                    if source.get("url") in sources:
                        candidate_sources.append(sources[source["url"]])
                # An uncited reason is still displayed beside its candidate.
                # Keep its missing source explicit; currentness still requires
                # linked evidence and cannot be inferred from this reason.
                for source in candidate_sources or [None]:
                    facts.append(
                        {
                            **asset,
                            **provenance,
                            "source": source,
                            "citation_url": source["url"] if source else None,
                            "citation_origin": "retrieved" if source else None,
                            "reason": candidate.reason_text,
                        }
                    )
        followup = _dict(_dict(effect.get("research")).get("follow_up"))
        for raw_asset in followup.get("subjects", []):
            asset = _asset(raw_asset)
            if asset is not None and (asset["symbol"], asset["name"]) in result_assets:
                owners.append(asset)
        for row in result.rows:
            facts.append(
                {
                    "symbol": row.symbol,
                    "name": row.subject,
                    **provenance,
                    "source": sources.get(row.source_url),
                    "citation_url": row.source_url,
                    "citation_origin": "retrieved"
                    if row.source_url in sources
                    else "model"
                    if row.source_url
                    else None,
                    "figure": row.model_dump(mode="json"),
                }
            )

    selected: list[dict] = []
    errors = []
    for raw_candidate in _dict(final_patch.get("discovery")).get("candidates", []):
        candidate = _asset(raw_candidate)
        if candidate is not None and candidate in owners:
            selected.append(candidate)
        else:
            errors.append("asset_class or identity unproven for a delivered candidate")
    for row in _dict(final_patch.get("next_experiments")).get("rows", []):
        parts = _dict(row).get("label_parts", [])
        tickers = [
            (index, part)
            for index, part in enumerate(parts)
            if _dict(part).get("type") == "ticker"
        ]
        if not tickers:
            errors.append("identity unproven for a delivered action")
        for index, part in tickers:
            matches = [
                asset
                for asset in owners
                if asset["symbol"] == part.get("value")
                and parts[max(0, index - 1) : index + 1] == asset_label_parts([asset])
            ]
            unique = {tuple(sorted(asset.items())) for asset in matches}
            if len(unique) == 1:
                selected.append(dict(next(iter(unique))))
            else:
                errors.append("asset_class or identity unproven for a delivered action")

    assets = []
    for asset in selected:
        if any(item["identity"] == asset for item in assets):
            continue
        related = [
            fact
            for fact in facts
            if str(fact.get("symbol") or "").upper() == asset["symbol"].upper()
        ]
        mismatched = [
            fact
            for fact in related
            if not _same_entity(asset, name=fact["name"], symbol=fact["symbol"])
        ]
        if mismatched:
            errors.append(
                f"identity mismatch between cited entity and action for {asset['symbol']}"
            )
        assets.append(
            {"identity": asset, "facts": related, "identity_matches": not mismatched}
        )
    if not assets:
        errors.append("identity unproven: no completed result bound to selectable assets")
    return {
        "contract_version": SELECTION_CONTRACT_VERSION,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "assets": assets,
        "errors": list(dict.fromkeys(errors)),
    }


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def compare_selection(expected: dict, evidence: dict, failures: list[str]) -> None:
    failures.extend(f"asset_discovery: {error}" for error in evidence["errors"])
    observed = _timestamp(evidence.get("observed_at"))
    for asset in evidence["assets"]:
        identity = asset["identity"]
        expected_class = expected.get("asset_class_hint")
        if expected_class is not None and identity["asset_class"] != expected_class:
            failures.append(
                f"asset_discovery: asset_class expected {expected_class}, got {identity['asset_class']}"
            )
        if expected.get("needs_current_facts") is not True:
            continue
        sourced = [
            fact
            for fact in asset["facts"]
            if fact.get("source") or fact.get("citation_url")
        ]
        if not sourced:
            failures.append(
                f"asset_discovery: current-source evidence unproven for {identity['symbol']}"
            )
            continue
        current = []
        for fact in sourced:
            try:
                policy = ResearchEvidencePolicy.model_validate(
                    fact.get("evidence_policy")
                )
            except ValidationError:
                continue
            retrieved = _timestamp(fact.get("retrieved_at"))
            if observed is None or retrieved is None:
                continue
            if not 0 <= (observed - retrieved).total_seconds() <= policy.max_age_seconds:
                continue
            source = ResearchSource.model_validate(
                fact["source"] if fact.get("source") else {"url": fact["citation_url"]}
            )
            current.extend(policy.select_sources([source]))
        if not current:
            failures.append(
                f"asset_discovery: currentness unproven for {identity['symbol']}"
            )


def selection_offered(offered: dict, evidence: dict) -> dict:
    assets = [item["identity"] for item in evidence["assets"] if item["identity_matches"]]
    return {
        **offered,
        "discovery_symbols": list(dict.fromkeys(asset["symbol"] for asset in assets)),
        "actionable": bool(
            assets or offered.get("recovery_option_ids") or offered.get("launch_payload")
        ),
    }


def selection_judge_context(evidence: dict) -> dict:
    """Keep typed facts and source evidence; exclude internal execution identities."""
    return {
        "contract_version": evidence["contract_version"],
        "observed_at": evidence["observed_at"],
        "assets": [
            {**item["identity"], "facts": item["facts"]} for item in evidence["assets"]
        ],
        "structural_errors": evidence["errors"],
    }
