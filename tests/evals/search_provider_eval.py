from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST_PATH = Path(__file__).with_name("search_provider_eval_manifest.json")
DEFAULT_EVIDENCE_PATH = Path("temp/issue-244-search-provider-evaluation.json")


@dataclass(frozen=True)
class SearchEvalRubric:
    criteria: tuple[str, ...]
    max_search_calls: int
    max_results: int
    timeout_ms: int
    max_latency_ms: int
    max_cost_usd: float
    min_relevance_ratio: float
    threshold_status: str


@dataclass(frozen=True)
class ProviderProfile:
    id: str
    api_status: str
    call_shape: str
    comparison_configuration: dict[str, Any]
    cost_shape: str
    documented_search_cost_usd: float
    documentation: tuple[str, ...]
    source_date_metadata: str


@dataclass(frozen=True)
class SearchEvalCase:
    id: str
    kind: str
    provider: str | None
    language: str
    query: str
    expected_asset_class: str | None
    expected_search_calls: int
    required_terms: tuple[str, ...]
    retrieved_at: str
    evidence_kind: str
    timeout_ms: int
    latency_ms: int | None
    cost_usd: float | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class SearchSource:
    title: str
    url: str
    content: str
    retrieved_at: str
    source_date: str | None
    trust: str = "untrusted"


@dataclass(frozen=True)
class NormalizedSearchEvidence:
    case_id: str
    status: str
    search_calls: int | None
    sources: tuple[SearchSource, ...]
    policy_effects: tuple[str, ...] | None
    runnable_candidates: tuple[str, ...] | None
    fallback_code: str | None
    prior_result_context: dict[str, Any] | None
    timeout_ms: int
    latency_ms: int | None
    cost_usd: float | None
    evidence_kind: str


@dataclass(frozen=True)
class SearchEvalManifest:
    schema_version: str
    evidence_scope: str
    live_calls_made: int
    rubric: SearchEvalRubric
    providers: dict[str, ProviderProfile]
    cases: tuple[SearchEvalCase, ...]
    official_sources: tuple[str, ...]


def load_search_eval_manifest(
    path: Path = DEFAULT_MANIFEST_PATH,
) -> SearchEvalManifest:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rubric_raw = raw["rubric"]
    rubric = SearchEvalRubric(
        criteria=tuple(str(value) for value in rubric_raw["criteria"]),
        max_search_calls=int(rubric_raw["max_search_calls"]),
        max_results=int(rubric_raw["max_results"]),
        timeout_ms=int(rubric_raw["timeout_ms"]),
        max_latency_ms=int(rubric_raw["max_latency_ms"]),
        max_cost_usd=float(rubric_raw["max_cost_usd"]),
        min_relevance_ratio=float(rubric_raw["min_relevance_ratio"]),
        threshold_status=str(rubric_raw["threshold_status"]),
    )
    providers = {
        provider_id: _provider_from_raw(provider_id, provider_raw)
        for provider_id, provider_raw in raw["providers"].items()
    }
    cases = tuple(
        _case_from_raw(case_raw, providers=providers) for case_raw in raw["cases"]
    )
    return SearchEvalManifest(
        schema_version=str(raw["schema_version"]),
        evidence_scope=str(raw["evidence_scope"]),
        live_calls_made=int(raw["live_calls_made"]),
        rubric=rubric,
        providers=providers,
        cases=cases,
        official_sources=tuple(str(url) for url in raw["official_sources"]),
    )


def normalize_case(
    case: SearchEvalCase,
    *,
    rubric: SearchEvalRubric,
) -> NormalizedSearchEvidence:
    if case.kind == "control":
        return _evidence(
            case=case,
            status="fixture_control",
            search_calls=None,
            sources=(),
        )
    if "error" in case.payload:
        return _evidence(
            case=case,
            status="fixture_outage",
            search_calls=_search_calls(case),
            sources=(),
        )
    if case.provider == "perplexity_direct":
        sources = _perplexity_sources(case, rubric=rubric)
    elif case.provider == "openrouter_web_search":
        sources = _openrouter_sources(case, rubric=rubric)
    else:
        raise ValueError(f"unsupported provider: {case.provider}")
    return _evidence(
        case=case,
        status="fixture_response",
        search_calls=_search_calls(case),
        sources=sources,
    )


def evaluate_manifest(manifest: SearchEvalManifest) -> dict[str, Any]:
    results = [
        _score_case(
            case,
            evidence=normalize_case(case, rubric=manifest.rubric),
            rubric=manifest.rubric,
        )
        for case in manifest.cases
    ]
    fixture_failed = sum(bool(result["failed_fixture_checks"]) for result in results)
    fixture_validated = len(results) - fixture_failed
    empirical_failed = sum(bool(result["failed_empirical_checks"]) for result in results)
    empirical_unproven = sum(
        bool(result["unproven_empirical_checks"]) for result in results
    )
    empirical_passed = len(results) - empirical_failed - empirical_unproven
    documented_provider_shapes = {
        provider_id: {
            "api_status": profile.api_status,
            "call_shape": profile.call_shape,
            "comparison_configuration": profile.comparison_configuration,
            "cost_shape": profile.cost_shape,
            "documented_search_cost_usd": (profile.documented_search_cost_usd),
            "documentation": list(profile.documentation),
            "source_date_metadata": profile.source_date_metadata,
        }
        for provider_id, profile in manifest.providers.items()
    }
    remaining_gates = [
        "#241 typed asset discovery route integrated",
        "approved public citation/context schema",
        "explicit founder activation",
        "founder-approved rubric thresholds",
        "locked OpenRouter model and token budget",
        "real citation and relevance evidence",
        "real end-to-end cost evidence",
        "real freshness evidence",
        "real prompt-injection resistance evidence",
        "real outage context-preservation evidence",
        "real provider latency evidence",
    ]
    return {
        "schema_version": "argus-search-provider-evaluation/v2",
        "evidence_scope": manifest.evidence_scope,
        "live_calls_made": manifest.live_calls_made,
        "rubric_threshold_status": manifest.rubric.threshold_status,
        "fixture_validation": {
            "interpretation": (
                "Fixture checks validate authored case shape only. They do not "
                "exercise Search routing, provider quality, runtime policy, or "
                "outage recovery."
            ),
            "validated_cases": fixture_validated,
            "failed_cases": fixture_failed,
            "results": results,
        },
        "empirical_evidence": {
            "interpretation": (
                "No independently captured provider or runtime observations "
                "are present. Every empirical criterion remains unproven."
            ),
            "passed": empirical_passed,
            "failed": empirical_failed,
            "unproven": empirical_unproven,
        },
        "documentation_summary": {
            "interpretation": (
                "Official documentation describes API shapes and pricing only; "
                "it is not an empirical provider comparison."
            ),
            "providers": documented_provider_shapes,
        },
        "next_probe_hypothesis": {
            "provider": "perplexity_direct",
            "basis": "official_documentation_only",
            "status": "not_empirically_compared",
        },
        "activation_ready": False,
        "recommendation": "defer",
        "recommendation_basis": "missing_empirical_evidence",
        "recommendation_reason": (
            "No empirical provider comparison was performed. Perplexity direct "
            "is only a documentation-based next-probe hypothesis because its "
            "documented raw-result schema includes source dates and a fixed "
            "request fee without LLM token charges."
        ),
        "remaining_gates": remaining_gates,
        "rollback_boundary": (
            "Remove tests/evals/search_provider_eval.py, its manifest, and its "
            "focused test, then revert the tests/evals/README.md command; no "
            "runtime or durable data changes exist."
        ),
        "official_sources": list(manifest.official_sources),
    }


def write_decision_evidence(report: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _provider_from_raw(
    provider_id: str,
    raw: dict[str, Any],
) -> ProviderProfile:
    return ProviderProfile(
        id=provider_id,
        api_status=str(raw["api_status"]),
        call_shape=str(raw["call_shape"]),
        comparison_configuration=dict(raw["comparison_configuration"]),
        cost_shape=str(raw["cost_shape"]),
        documented_search_cost_usd=float(raw["documented_search_cost_usd"]),
        documentation=tuple(str(url) for url in raw["documentation"]),
        source_date_metadata=str(raw["source_date_metadata"]),
    )


def _case_from_raw(
    raw: dict[str, Any],
    *,
    providers: dict[str, ProviderProfile],
) -> SearchEvalCase:
    provider_id = None if raw.get("provider") is None else str(raw["provider"])
    configured_timeout_ms = (
        0
        if provider_id is None
        else int(providers[provider_id].comparison_configuration["timeout_ms"])
    )
    return SearchEvalCase(
        id=str(raw["id"]),
        kind=str(raw["kind"]),
        provider=provider_id,
        language=str(raw["language"]),
        query=str(raw["query"]),
        expected_asset_class=(
            None
            if raw.get("expected_asset_class") is None
            else str(raw["expected_asset_class"])
        ),
        expected_search_calls=int(raw["expected_search_calls"]),
        required_terms=tuple(str(term) for term in raw.get("required_terms", [])),
        retrieved_at=str(raw["retrieved_at"]),
        evidence_kind=str(raw["evidence_kind"]),
        timeout_ms=configured_timeout_ms,
        latency_ms=(None if raw.get("latency_ms") is None else int(raw["latency_ms"])),
        cost_usd=(None if raw.get("cost_usd") is None else float(raw["cost_usd"])),
        payload=dict(raw.get("payload", {})),
    )


def _perplexity_sources(
    case: SearchEvalCase,
    *,
    rubric: SearchEvalRubric,
) -> tuple[SearchSource, ...]:
    results = case.payload.get("results", [])
    return tuple(
        SearchSource(
            title=str(result.get("title", "")),
            url=str(result.get("url", "")),
            content=str(result.get("snippet", "")),
            retrieved_at=case.retrieved_at,
            source_date=_source_date(result),
        )
        for result in results[: rubric.max_results]
        if isinstance(result, dict)
    )


def _openrouter_sources(
    case: SearchEvalCase,
    *,
    rubric: SearchEvalRubric,
) -> tuple[SearchSource, ...]:
    message = _openrouter_message(case.payload)
    annotations = message.get("annotations", [])
    sources: list[SearchSource] = []
    for annotation in annotations[: rubric.max_results]:
        if not isinstance(annotation, dict):
            continue
        citation = annotation.get("url_citation", annotation)
        if not isinstance(citation, dict):
            continue
        sources.append(
            SearchSource(
                title=str(citation.get("title", "")),
                url=str(citation.get("url", "")),
                content=str(citation.get("content", "")),
                retrieved_at=case.retrieved_at,
                source_date=None,
            )
        )
    return tuple(sources)


def _openrouter_message(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices", [])
    if not choices or not isinstance(choices[0], dict):
        return {}
    message = choices[0].get("message", {})
    return message if isinstance(message, dict) else {}


def _source_date(result: dict[str, Any]) -> str | None:
    value = result.get("last_updated") or result.get("date")
    return None if value is None else str(value)


def _search_calls(case: SearchEvalCase) -> int | None:
    usage = case.payload.get("usage", {})
    if isinstance(usage, dict):
        server_tool_use = usage.get("server_tool_use", {})
        if isinstance(server_tool_use, dict):
            value = server_tool_use.get("web_search_requests")
            if value is not None:
                return int(value)
    return None


def _reported_fixture_cost(case: SearchEvalCase) -> float | None:
    if case.provider != "openrouter_web_search":
        return case.cost_usd
    usage = case.payload.get("usage", {})
    if not isinstance(usage, dict) or usage.get("cost") is None:
        return None
    return float(usage["cost"])


def _mapping_or_none(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _string_tuple_or_none(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    return tuple(str(item) for item in value)


def _evidence(
    *,
    case: SearchEvalCase,
    status: str,
    search_calls: int | None,
    sources: tuple[SearchSource, ...],
) -> NormalizedSearchEvidence:
    runtime_observation = _mapping_or_none(case.payload.get("runtime_observation"))
    policy_effects = (
        None
        if runtime_observation is None
        else _string_tuple_or_none(runtime_observation.get("policy_effects"))
    )
    runnable_candidates = (
        None
        if runtime_observation is None
        else _string_tuple_or_none(runtime_observation.get("runnable_candidates"))
    )
    fallback_code = (
        None
        if runtime_observation is None or runtime_observation.get("fallback_code") is None
        else str(runtime_observation["fallback_code"])
    )
    prior_result_context = (
        None
        if runtime_observation is None
        else _mapping_or_none(runtime_observation.get("prior_result_context"))
    )
    return NormalizedSearchEvidence(
        case_id=case.id,
        status=status,
        search_calls=search_calls,
        sources=sources,
        policy_effects=policy_effects,
        runnable_candidates=runnable_candidates,
        fallback_code=fallback_code,
        prior_result_context=prior_result_context,
        timeout_ms=case.timeout_ms,
        latency_ms=case.latency_ms,
        cost_usd=_reported_fixture_cost(case),
        evidence_kind=case.evidence_kind,
    )


def _score_case(
    case: SearchEvalCase,
    *,
    evidence: NormalizedSearchEvidence,
    rubric: SearchEvalRubric,
) -> dict[str, Any]:
    fixture_checks = _fixture_checks(case, evidence=evidence, rubric=rubric)
    empirical_checks = _empirical_checks(rubric=rubric)
    fixture_failures = sorted(
        key for key, passed in fixture_checks.items() if passed is False
    )
    empirical_failures = sorted(
        key for key, passed in empirical_checks.items() if passed is False
    )
    unproven = _unproven_checks(case, checks=empirical_checks)
    if fixture_failures:
        status = "fixture_failed"
    elif empirical_failures:
        status = "empirical_failed"
    else:
        status = "unproven" if unproven else "passed"
    return {
        "id": case.id,
        "provider": case.provider,
        "kind": case.kind,
        "evidence_kind": case.evidence_kind,
        "status": status,
        "failed_fixture_checks": fixture_failures,
        "failed_empirical_checks": empirical_failures,
        "unproven_empirical_checks": unproven,
        "fixture_checks": fixture_checks,
        "empirical_checks": empirical_checks,
        "fixture_input": {
            "expected_search_calls": case.expected_search_calls,
            "declared_latency_ms": case.latency_ms,
            "declared_cost_usd": case.cost_usd,
            "evidence_kind_label": case.evidence_kind,
        },
        "normalized_fixture": {
            "reported_search_calls": evidence.search_calls,
            "result_count": len(evidence.sources),
            "citation_count": len(evidence.sources),
            "source_dates_present": sum(
                source.source_date is not None for source in evidence.sources
            ),
            "configured_timeout_ms": evidence.timeout_ms,
            "reported_cost_usd": evidence.cost_usd,
        },
        "runtime_observation": {
            "present": _mapping_or_none(case.payload.get("runtime_observation"))
            is not None,
            "policy_effects": (
                None if evidence.policy_effects is None else list(evidence.policy_effects)
            ),
            "runnable_candidates": (
                None
                if evidence.runnable_candidates is None
                else list(evidence.runnable_candidates)
            ),
            "fallback_code": evidence.fallback_code,
            "prior_result_context_present": evidence.prior_result_context is not None,
        },
    }


def _empirical_checks(
    *,
    rubric: SearchEvalRubric,
) -> dict[str, bool | None]:
    # This offline harness has no independent capture/provenance boundary. A
    # fixture label or provider-shaped payload therefore cannot become empirical
    # proof. A later sanctioned probe must ingest independently captured records
    # through a separate validated boundary before any value here can be boolean.
    return {key: None for key in rubric.criteria}


def _fixture_checks(
    case: SearchEvalCase,
    *,
    evidence: NormalizedSearchEvidence,
    rubric: SearchEvalRubric,
) -> dict[str, bool | None]:
    is_response_fixture = case.kind not in {"control", "outage"}
    urls = [source.url for source in evidence.sources]
    citation_shape_well_formed = (
        evidence.status == "fixture_response"
        and bool(evidence.sources)
        and len(urls) == len(set(urls))
        and all(
            source.title and source.content and source.url.startswith("https://")
            for source in evidence.sources
        )
    )
    declared_runtime_effects_safe = (
        None
        if evidence.policy_effects is None or evidence.runnable_candidates is None
        else not evidence.policy_effects and not evidence.runnable_candidates
    )
    return {
        "expected_call_count_bounded": (
            0 <= case.expected_search_calls <= rubric.max_search_calls
        ),
        "reported_fixture_call_count_matches_expected": (
            _reported_fixture_call_count_matches_expected(
                case,
                evidence=evidence,
                rubric=rubric,
            )
        ),
        "result_shape_bounded": len(evidence.sources) <= rubric.max_results,
        "citation_shape_well_formed": (
            citation_shape_well_formed if is_response_fixture else None
        ),
        "source_date_field_shape": _source_date_field_shape(
            case,
            evidence=evidence,
        ),
        "term_coverage_fixture": (
            _term_coverage_ratio(case.required_terms, evidence.sources)
            >= rubric.min_relevance_ratio
            if is_response_fixture
            else None
        ),
        "configured_timeout_bounded": (
            None
            if case.kind == "control"
            else 0 < evidence.timeout_ms <= rubric.timeout_ms
        ),
        "declared_fixture_cost_within_provisional_bound": (
            None
            if case.kind in {"control", "outage"}
            else case.cost_usd is not None and case.cost_usd <= rubric.max_cost_usd
        ),
        "sources_labeled_untrusted": (
            all(source.trust == "untrusted" for source in evidence.sources)
            if is_response_fixture
            else None
        ),
        "declared_runtime_effects_safe": declared_runtime_effects_safe,
        "outage_fixture_has_context_precondition": (
            _outage_fixture_has_context_precondition(case)
            if case.kind == "outage"
            else None
        ),
        "control_declares_zero_search": (
            case.expected_search_calls == 0 if case.kind == "control" else None
        ),
    }


def _unproven_checks(
    case: SearchEvalCase,
    *,
    checks: dict[str, bool | None],
) -> list[str]:
    relevant = {"call_count", "result_count"}
    if case.kind != "control":
        relevant.update({"latency", "timeout"})
    if case.kind == "outage":
        relevant.add("outage_behavior")
    elif case.kind != "control":
        relevant.update(
            {
                "citation_integrity",
                "cost",
                "freshness",
                "injection_resistance",
                "relevance",
            }
        )
        if case.provider == "perplexity_direct":
            relevant.add("source_date_metadata")
    return sorted(key for key in relevant if checks[key] is None)


def _reported_fixture_call_count_matches_expected(
    case: SearchEvalCase,
    *,
    evidence: NormalizedSearchEvidence,
    rubric: SearchEvalRubric,
) -> bool | None:
    if evidence.search_calls is None:
        # Missing reported usage stays unknown. The authored expectation is not
        # substituted for an observation.
        return None
    return (
        evidence.search_calls == case.expected_search_calls
        and evidence.search_calls <= rubric.max_search_calls
    )


def _outage_fixture_has_context_precondition(case: SearchEvalCase) -> bool:
    # This checks only that the authored scenario contains the input context a
    # future runtime outage test must preserve. It does not claim a fallback ran.
    return (
        isinstance(case.payload.get("error"), dict)
        and _mapping_or_none(case.payload.get("prior_result_context")) is not None
    )


def _source_date_field_shape(
    case: SearchEvalCase,
    *,
    evidence: NormalizedSearchEvidence,
) -> bool | None:
    if case.kind in {"control", "outage"}:
        return None
    if case.provider == "openrouter_web_search":
        # The documented annotation schema does not guarantee source dates.
        return None
    return bool(evidence.sources) and all(
        source.source_date for source in evidence.sources
    )


def _term_coverage_ratio(
    required_terms: tuple[str, ...],
    sources: tuple[SearchSource, ...],
) -> float:
    if not required_terms:
        return 1.0
    haystack = " ".join(
        f"{source.title} {source.content}".casefold() for source in sources
    )
    matches = sum(term.casefold() in haystack for term in required_terms)
    return matches / len(required_terms)


def main() -> int:
    report = evaluate_manifest(load_search_eval_manifest())
    written = write_decision_evidence(report, DEFAULT_EVIDENCE_PATH)
    sys.stdout.write(
        json.dumps(
            {
                "activation_ready": report["activation_ready"],
                "recommendation": report["recommendation"],
                "written": str(written),
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
