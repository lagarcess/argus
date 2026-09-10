"""Read-only scorecard comparison. All outputs stay in the supplied output folder."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


def read(path: Path):
    return json.loads(path.read_text(), parse_float=Decimal)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def hash_file(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n")


def family(check):
    # A display grouping only. Exact original checks remain alongside it.
    if check.startswith("prose_judge:"):
        return check
    return check.split(":", 1)[0]


def observation(row):
    typed = row.get("typed_outcome") or {}
    fields = ("primary_intent", "intent", "tool_calls", "tool_call_records")
    calls = typed.get("tool_calls")
    records = typed.get("tool_call_records")
    selection = typed.get("asset_discovery")
    return {
        "status": row["status"],
        "failed_checks": row.get("failed_checks", []),
        "infrastructure_errors": row.get("infrastructure_errors", []),
        "observation_fields_present": {field: field in typed for field in fields},
        "primary_intent": typed.get("primary_intent"),
        "effective_intent": typed.get("intent"),
        "tool_call_count": None if calls is None else len(calls),
        "tool_names": None if calls is None else [call["tool_name"] for call in calls],
        "tool_record_count": None if records is None else len(records),
        "tool_record_outcomes": None if records is None else [
            {"tool_name": record["tool_name"], "outcome": record["outcome"]}
            for record in records
        ],
        "raw_stage_outcomes": typed.get("stage_outcomes"),
        "acceptance_stage_outcomes": typed.get("acceptance_stage_outcomes"),
        "execution_trace": typed.get("execution_trace"),
        "selection_contract_version": selection.get("contract_version") if isinstance(selection, dict) else None,
        "prose_requested_criteria": (row.get("prose_judge") or {}).get("requested_criteria"),
        "prose_failed_criteria": (row.get("prose_judge") or {}).get("failed_criteria"),
    }


def summary(doc):
    rows = doc["results"]
    obs = [observation(row) for row in rows]
    calls = [o for o in obs if o["tool_call_count"] is not None]
    records = [o for o in obs if o["tool_record_count"] is not None]
    return {
        "totals_as_recorded": doc["totals"],
        "case_count": len(rows),
        "status_counts": dict(Counter(row["status"] for row in rows)),
        "failed_check_count": sum(len(row.get("failed_checks", [])) for row in rows),
        "failed_check_family_counts": dict(Counter(family(check) for row in rows for check in row.get("failed_checks", []))),
        "effective_intent_counts": dict(Counter(str(o["effective_intent"]) for o in obs)),
        "primary_intent_field_present_case_count": sum(o["observation_fields_present"]["primary_intent"] for o in obs),
        "primary_intent_counts": dict(Counter(str(o["primary_intent"]) for o in obs if o["observation_fields_present"]["primary_intent"])),
        "tool_calls_observed_case_count": len(calls),
        "tool_calls_unobserved_case_count": len(rows) - len(calls),
        "tool_call_count_histogram": dict(Counter(str(o["tool_call_count"]) for o in calls)),
        "selected_call_total": sum(o["tool_call_count"] for o in calls),
        "selected_tool_counts": dict(Counter(name for o in calls for name in o["tool_names"])),
        "tool_records_observed_case_count": len(records),
        "tool_record_count_histogram": dict(Counter(str(o["tool_record_count"]) for o in records)),
        "tool_record_total": sum(o["tool_record_count"] for o in records),
        "tool_record_outcome_counts": dict(Counter(r["outcome"] for o in records for r in o["tool_record_outcomes"])),
        "selected_without_record_cases": [row["id"] for row, o in zip(rows, obs) if o["tool_call_count"] and not o["tool_record_count"]],
        "multiple_call_cases": [row["id"] for row, o in zip(rows, obs) if (o["tool_call_count"] or 0) > 1],
        "repeated_tool_cases": [row["id"] for row, o in zip(rows, obs) if o["tool_names"] and len(set(o["tool_names"])) < len(o["tool_names"])],
        "selection_contract_version_counts": dict(Counter(o["selection_contract_version"] for o in obs if o["selection_contract_version"])),
        "provider_usage_as_recorded": doc.get("provider_usage"),
    }


def compare(baseline, candidate):
    old = {r["id"]: r for r in baseline["results"]}
    new = {r["id"]: r for r in candidate["results"]}
    common = sorted(old.keys() & new.keys())
    cases = []
    for case in common:
        before, after = observation(old[case]), observation(new[case])
        oldchecks, newchecks = set(before["failed_checks"]), set(after["failed_checks"])
        cases.append({
            "id": case,
            "baseline": before,
            "candidate": after,
            "unchanged_failed_checks": sorted(oldchecks & newchecks),
            "baseline_only_failed_checks": sorted(oldchecks - newchecks),
            "candidate_only_failed_checks": sorted(newchecks - oldchecks),
            "baseline_check_families": sorted({family(c) for c in oldchecks}),
            "candidate_check_families": sorted({family(c) for c in newchecks}),
        })
    transitions = Counter(f"{old[i]['status']} -> {new[i]['status']}" for i in common)
    return {
        "common_case_count": len(common),
        "added_cases": sorted(new.keys() - old.keys()),
        "removed_cases": sorted(old.keys() - new.keys()),
        "fixture_hash_equal": baseline["provenance"].get("fixture_sha256") == candidate["provenance"].get("fixture_sha256"),
        "status_transition_counts": dict(transitions),
        "passed_to_failed": [i for i in common if old[i]["status"] == "passed" and new[i]["status"] == "failed"],
        "failed_to_passed": [i for i in common if old[i]["status"] == "failed" and new[i]["status"] == "passed"],
        "failed_in_both": [i for i in common if old[i]["status"] == new[i]["status"] == "failed"],
        "cases": cases,
    }


def parse_log(path):
    agent_events = {}
    route_receipts = []
    completions = []
    current_case = None
    total_billing_lines = 0
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if line.startswith('{"event":'):
            event = json.loads(line)
            if event["event"] == "case_started":
                current_case = event["case"]
            elif event["event"] == "case_completed":
                completions.append(event)
                assert current_case == event["case"]
                current_case = None
        if "OpenRouter route receipt " in line:
            receipt = json.loads(line.split("OpenRouter route receipt ", 1)[1], parse_float=Decimal)
            route_receipts.append({"case_id": current_case, "line": lineno, "receipt": receipt})
        if " - research_cost_unpriced " in line or " - research_cost_unrecorded " in line:
            raw = json.loads(line[line.index("{"):], parse_float=Decimal)
            key = raw["provider_response_id"]
            assert key, "Cannot safely deduplicate an invoice without its response identity"
            total_billing_lines += 1
            if key in agent_events:
                assert agent_events[key]["raw"] == raw
                assert agent_events[key]["case_id"] == current_case
                agent_events[key]["log_lines"].append(lineno)
            else:
                agent_events[key] = {"raw": raw, "case_id": current_case, "log_lines": [lineno]}
    invoices = []
    for key, event in agent_events.items():
        raw = event["raw"]
        # Keep private financial facts; a hash proves deduplication without exposing the raw provider id.
        invoices.append({
            "provider_response_id_sha256": hashlib.sha256(key.encode()).hexdigest(),
            "case_id": event["case_id"],
            "case_binding_basis": "between explicit case_started and case_completed log events",
            "log_lines": event["log_lines"],
            **{k: v for k, v in raw.items() if k != "provider_response_id"},
        })
    return route_receipts, invoices, total_billing_lines, completions


def sum_money(values):
    return sum((Decimal(str(v)) for v in values if v is not None), Decimal(0))


def costs(candidate, logfile):
    rows = candidate["results"]
    receipts = [(row["id"], i, receipt) for row in rows for i, receipt in enumerate(row.get("route_receipts", []))]
    logreceipts, invoices, billing_lines, completions = parse_log(logfile)
    def receipt_key(case, receipt):
        return (case, receipt["created_at"], receipt["task"], receipt["model"], receipt["schema_name"])
    score_by_key = {receipt_key(case, receipt): receipt for case, _, receipt in receipts}
    log_by_key = {receipt_key(r["case_id"], r["receipt"]): r["receipt"] for r in logreceipts}
    assert len(score_by_key) == len(receipts) and len(log_by_key) == len(logreceipts)
    assert score_by_key.keys() == log_by_key.keys(), "Log/scorecard receipt identities differ"
    changed_fields = Counter(
        field for key in score_by_key
        for field in score_by_key[key].keys() | log_by_key[key].keys()
        if score_by_key[key].get(field) != log_by_key[key].get(field)
    )
    # Repair effects are annotated after the initial receipt log event. All billing and identity facts must match.
    assert set(changed_fields) <= {"repair_effect"}, "Unexpected receipt mismatch; do not combine sources"
    assert len(completions) == len(rows)
    assert {e["case"]: (e["status"], e.get("failed_checks", [])) for e in completions} == {r["id"]: (r["status"], r.get("failed_checks", [])) for r in rows}
    priced = [(case, i, r) for case, i, r in receipts if r.get("usage_cost_usd") is not None]
    unpriced = [(case, i, r) for case, i, r in receipts if r.get("usage_cost_usd") is None]
    or_total = sum_money(r["usage_cost_usd"] for _, _, r in priced)
    assert or_total == candidate["provider_usage"]["reported_cost_usd"]
    assert len(receipts) == candidate["provider_usage"]["route_receipt_count"]
    assert len(priced) == candidate["provider_usage"]["reported_cost_receipt_count"]
    assert len(unpriced) == candidate["provider_usage"]["unreported_cost_receipt_count"]
    tool_usage = [{"case_id": row["id"], **u} for row in rows for u in row.get("typed_outcome", {}).get("tool_usage", [])]
    assert len({(u["case_id"], u["call_id"]) for u in tool_usage}) == len(tool_usage)
    # Non-null charges in this scorecard are separate Search API receipts. No per-tool request classifier is used.
    numeric_usage = [u for u in tool_usage if u["usage"].get("cost_usd") is not None]
    search_total = sum_money(u["usage"]["cost_usd"] for u in numeric_usage)
    invoice_cases = {invoice["case_id"] for invoice in invoices}
    assert not invoice_cases & {u["case_id"] for u in numeric_usage}, "Potential overlapping research charges require manual review"
    assert all(i["reported_cost"]["currency"] == "USD" for i in invoices)
    agent_total = sum_money(i["reported_cost"]["total_cost"] for i in invoices)
    components = {name: sum_money(i["reported_cost"].get(name) for i in invoices) for name in ["input_cost", "output_cost", "cache_creation_cost", "cache_read_cost", "tool_calls_cost"]}
    assert sum_money(components.values()) == agent_total
    bycase = []
    for row in rows:
        case = row["id"]
        case_receipts = [r for c, _, r in receipts if c == case]
        case_invoices = [i for i in invoices if i["case_id"] == case]
        case_usages = [u for u in tool_usage if u["case_id"] == case]
        amounts = {
            "openrouter_reported_usd": sum_money(r.get("usage_cost_usd") for r in case_receipts),
            "search_recorded_estimate_usd": sum_money(u["usage"].get("cost_usd") for u in case_usages),
            "agent_provider_reported_unvalidated_usd": sum_money(i["reported_cost"]["total_cost"] for i in case_invoices),
        }
        bycase.append({"case_id": case, **amounts, "accounted_usd": sum_money(amounts.values()), "unknown_openrouter_record_count": sum(r.get("usage_cost_usd") is None for r in case_receipts), "research_invoice_count": len(case_invoices)})
    return {
        "currency": "USD",
        "amount_encoding": "Exact base-10 strings; Decimal sums avoid binary float drift",
        "openrouter": {
            "reported_usd": or_total,
            "priced_records": len(priced),
            "unpriced_records": len(unpriced),
            "total_records": len(receipts),
            "scorecard_billing_and_identity_match_log_exactly": True,
            "post_log_metadata_difference_counts": dict(changed_fields),
            "zero_latency_unpriced_record_count": sum(r.get("latency_ms") == 0 for _, _, r in unpriced),
            "nonzero_latency_unpriced_record_count": sum(r.get("latency_ms") != 0 for _, _, r in unpriced),
            "unpriced_with_token_usage_count": sum(r.get("token_usage") is not None for _, _, r in unpriced),
            "unpriced_failure_mode_counts": dict(Counter(r.get("failure_mode") for _, _, r in unpriced)),
            "unpriced_records_evidence": [{"case_id": case, "receipt_index": idx, **{key: r.get(key) for key in ["created_at", "task", "schema_name", "model", "fallback_used", "outcome", "failure_mode", "latency_ms", "token_usage", "usage_cost_usd"]}} for case, idx, r in unpriced],
            "warning": "Records are not unique provider requests. Fifteen zero-latency local rejection records are not fifteen additional provider calls. Null costs are unavailable, not zero.",
        },
        "separate_search_api": {
            "non_null_tool_usage_count": len(numeric_usage),
            "recorded_estimate_usd": search_total,
            "basis": "The three retained non-null tool_usage charges each equal the configured direct Search API fee of $0.005. This is the runtime's documented fee estimate, not an invoice validated here.",
            "source_owner": "src/argus/domain/research/search/perplexity_direct.py:21,62; src/argus/agent_runtime/research_find.py:177-179",
        },
        "research_agent": {
            "billing_log_line_count": billing_lines,
            "unique_provider_response_count": len(invoices),
            "duplicate_log_line_count_excluded": billing_lines - len(invoices),
            "provider_reported_usd": agent_total,
            "tariff_validated_usd": None,
            "reported_component_totals_usd": components,
            "reason_counts": dict(Counter(i["reason"] for i in invoices)),
            "embedded_tool_invocations": {k: sum(i["usage"].get(k) or 0 for i in invoices) for k in ["finance_search_invocations", "web_search_invocations", "fetch_url_invocations"]},
            "unique_invoices": invoices,
            "warning": "All four invoices have rate_mismatch and cost_usd=null. Provider-reported totals are disclosed separately, not accepted as validated tariff costs. Embedded search/fetch charges are already included in those totals.",
        },
        "tool_usage_as_recorded": tool_usage,
        "tool_usage_cache_status_counts": dict(Counter(u["usage"].get("cache_status") for u in tool_usage)),
        "accounted_reported_and_estimated_total_usd": or_total + search_total + agent_total,
        "validated_or_recorded_excluding_mismatched_agent_usd": or_total + search_total,
        "unknown_or_unvalidated_cost_remains": True,
        "by_case": bycase,
        "double_count_controls": [
            "All 381 OpenRouter log/scorecard receipt identities, costs, tokens and outcomes match. Forty later repair_effect annotations differ; no billing fact differs. One source is counted, never both.",
            "Duplicate unpriced/unrecorded events are grouped by provider response identity; payload equality is asserted.",
            "Only non-null numeric tool_usage is added; its cases do not overlap with provider invoice cases.",
            "No second fee is added for finance_search, web_search, or fetch_url inside Agent invoices.",
            "Research invocations is finance_search count, not total Agent requests; zero does not imply free/no provider work.",
            "The stale initial /private/tmp/registry-research-billing.json is excluded.",
        ],
    }


def markdown(comparison, accounting):
    lines = [
        "# Third registry measurement: preserved comparison",
        "",
        f"Clean measured candidate `{comparison['inputs']['third']['provenance']['candidate_sha']}`: **49 passed, 19 failed, 0 infrastructure errors, 0 skipped**, across 68 cases. Original statuses and exact failed-check strings are preserved; this report does not regrade an earlier run.",
        "",
        "| Prior run | Recorded prior result | Common cases | Pass → fail | Fail → pass | Failed in both |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for name, item in comparison["comparisons"].items():
        total = comparison["summaries"][name]["totals_as_recorded"]
        lines.append(f"| {name} | {total.get('passed', 0)} pass / {total.get('failed', 0)} fail | {item['common_case_count']} | {len(item['passed_to_failed'])} | {len(item['failed_to_passed'])} | {len(item['failed_in_both'])} |")
    lines += ["", "The 411 run contains 62 cases; the other three runs contain the same 68 case IDs. Fixture hashes differ for 411 and 565. The second and third full runs have the same fixture hash, but the third uses collective selection evidence and the added evaluator-level selection-relevance criterion. These are recorded status transitions across different code/evaluation contracts, not isolated causal regression estimates.", "", "## Cases with a failed grade in the second or third full run", "", "P = passed, F = failed, absent = no case in that source. The final column groups exact third-run check strings for readability; comparison.json retains every string and per-case check delta.", "", "| Case ID | 411 | 565 | Second | Third | Third failed-check families |", "| --- | --- | --- | --- | --- | --- |"]
    for row in comparison["case_matrix"]:
        obs = row["runs"]
        if not any(obs.get(name, {}).get("status") == "failed" for name in ("second", "third")):
            continue
        statuses = [({"passed": "P", "failed": "F"}.get(obs.get(name, {}).get("status"), obs.get(name, {}).get("status", "absent"))) for name in ("411", "565", "second", "third")]
        checks = ", ".join(sorted({family(c) for c in obs["third"]["failed_checks"]})) or "—"
        lines.append(f"| `{row['id']}` | {' | '.join(statuses)} | {checks} |")
    lines += ["", "## Observed intents and calls", "", "| Observation | Third full run |", "| --- | --- |", "| Primary intent | calculate 44; explain 16; follow_up 1; cannot 6; null 1 |", "| Effective intent | calculate 45; explain 6; follow_up 11; cannot 6 |", "| Selected call counts | 34 cases with zero calls; 34 with one call; none with multiple calls |", "| Selected tools | backtest 24; peer_expansion 7; screening 2; balanced_lookup 1 |", "| Actual execution records | 10 research records: 9 succeeded, 1 unavailable |", "| Backtest execution records | 0; the 24 selected calls are preparation/confirmation observations, not executed simulations |", "", "All four canonical labels occur. Ten primary explain turns select a research call and finish with effective follow_up. This supports tool selection without forcing every call into calculate. It does not prove all seven historical intents were exercised: the 411/565 scorecards observe only four legacy labels and do not retain primary-intent or tool-call fields. Missing historical call fields are reported as unobserved, never as zero calls. This live suite has no multi-call or repeated-call turn, so it does not establish composition or repetition behavior. The 19 failures also prevent a claim of behavioral parity or a clear lane.", "", "## Cost disclosure", "", f"OpenRouter reports **${accounting['openrouter']['reported_usd']}** across 357 priced receipt records out of 381. The 24 records without costs comprise 6 timeouts, 3 validation errors and 15 zero-latency local rejection records; none retains token usage. These are not 24 extra requests.", "", f"Three separate Search API observations retain **${accounting['separate_search_api']['recorded_estimate_usd']}** in total, using the configured $0.005 fee. Four distinct Research Agent responses report **${accounting['research_agent']['provider_reported_usd']}** in invoices. All four have tariff mismatches, so that amount is provider-reported, not independently validated. Eight billing log lines describe those four responses; each duplicate is excluded. The invoices already include 1 finance-search, 14 web-search and 3 fetch-url invocations, so no additional embedded-tool fee is added.", "", f"The accounted reported/estimated total is **${accounting['accounted_reported_and_estimated_total_usd']}**. It already includes the unvalidated Agent invoices; additional spend behind missing-cost OpenRouter records remains unquantified. OpenRouter plus the separate Search estimate alone is **${accounting['validated_or_recorded_excluding_mismatched_agent_usd']}**. No per-request charge for market-data/asset-provider access is retained, so none is invented. The report is not a complete validated invoice.", "", "Detailed evidence: comparison.json (all case/check/intent observations), cost-accounting.json (exact decimal sums, per-case amounts and deduplication), provenance.json (input hashes), analyze_scorecards.py (reproducible read-only analysis)."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--baseline", action="append", required=True, help="NAME=PATH")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    assert out == Path('/private/tmp/registry-third-measurement-analysis')
    paths = {name: Path(path).resolve() for name, path in (value.split('=', 1) for value in args.baseline)}
    paths['third'] = args.candidate.resolve()
    docs = {name: read(path) for name, path in paths.items()}
    candidate = docs['third']
    for doc in docs.values():
        ids = [row['id'] for row in doc['results']]
        assert len(ids) == len(set(ids))
        assert set(ids) == set(doc['provenance']['fixture_case_ids'])
    assert candidate['provenance']['candidate_sha'] == '72aa04a06d00a76421414e778d67fc2cf3ccd0f2'
    assert candidate['provenance']['worktree_clean'] is True
    assert candidate['totals']['passed'] == 49 and candidate['totals']['failed'] == 19
    inputs = {name: {'path': str(path), 'sha256': hash_file(path), 'bytes': path.stat().st_size, 'generated_at': docs[name].get('generated_at'), 'provenance': docs[name]['provenance']} for name, path in paths.items()}
    comparison = {
        'analysis_contract': 'preserved-scorecard-comparison/v1',
        'not_a_regrade': True,
        'inputs': inputs,
        'summaries': {name: summary(doc) for name, doc in docs.items()},
        'comparisons': {name: compare(doc, candidate) for name, doc in docs.items() if name != 'third'},
        'case_matrix': [{'id': row['id'], 'category': row['category'], 'runs': {name: observation(old) for name, doc in docs.items() for old in doc['results'] if old['id'] == row['id']}} for row in candidate['results']],
        'comparability_limits': [
            'Original statuses and check strings are preserved; no prior scorecard is regraded.',
            'Fixture IDs allow case matching, not causal attribution across separate provider runs.',
            '411 and 565 do not retain primary intents or tool calls; absent fields are unobserved, not zero.',
            'The second and third fixture hashes match but evaluator observation/relevance contracts changed. Selection evidence is versioned in fresh results.',
            'Four canonical labels are observed, but live composition and repeated calls are not exercised.',
        ],
    }
    accounting = costs(candidate, args.log.resolve())
    out.mkdir(parents=True, exist_ok=True)
    dump(out / 'comparison.json', comparison)
    dump(out / 'cost-accounting.json', accounting)
    (out / 'README.md').write_text(markdown(comparison, accounting))
    provenance = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'candidate_sha_from_scorecard': candidate['provenance']['candidate_sha'],
        'candidate_clean_from_scorecard': candidate['provenance']['worktree_clean'],
        'inputs': inputs,
        'log': {'path': str(args.log.resolve()), 'sha256': hash_file(args.log.resolve()), 'bytes': args.log.stat().st_size},
        'adaptation_basis': {'path': '/private/tmp/registry-compare-scorecards.py', 'sha256': hash_file(Path('/private/tmp/registry-compare-scorecards.py')), 'changes': 'Replace hardcoded 411/565/output paths with explicit inputs; add second full run, exact checks, missing-field-safe observations, log cost reconciliation and immutable input hashes.'},
        'analysis_constraints': 'No runtime imports, network, provider calls, checkout edits, Git operations or fixture/scorecard mutation. Outputs only inside assigned temp folder.',
        'cost_sum_assertions_passed': True,
        'case_log_scorecard_grade_equality_asserted': True,
        'route_log_scorecard_billing_identity_equality_asserted': True,
        'post_log_repair_effect_annotation_difference_count': accounting['openrouter']['post_log_metadata_difference_counts'].get('repair_effect', 0),
        'source_owner_bytes_as_read': {str(path): {'sha256': hash_file(path), 'note': 'Current read-only owner evidence, not a new measured runtime claim'} for path in [args.root / 'src/argus/domain/research/search/perplexity_direct.py', args.root / 'src/argus/domain/research/billing.py', args.root / 'src/argus/domain/research/perplexity_agent.py', args.root / 'tests/evals/measurement_registry.py', args.root / 'src/argus/agent_runtime/state/models.py', args.root / 'docs/reports/evidence/registry/verification/selection-acceptance.md']},
        'artifacts': {name: {'sha256': hash_file(out / name), 'bytes': (out / name).stat().st_size} for name in ['comparison.json', 'cost-accounting.json', 'README.md', 'analyze_scorecards.py']},
    }
    dump(out / 'provenance.json', provenance)
    print(json.dumps({'totals': candidate['totals'], 'transitions': {name: data['status_transition_counts'] for name, data in comparison['comparisons'].items()}, 'accounted_usd': accounting['accounted_reported_and_estimated_total_usd'], 'outputs': [str(out / name) for name in ['comparison.json', 'cost-accounting.json', 'README.md', 'provenance.json', 'analyze_scorecards.py']]}, default=str, indent=2))


if __name__ == '__main__':
    main()
