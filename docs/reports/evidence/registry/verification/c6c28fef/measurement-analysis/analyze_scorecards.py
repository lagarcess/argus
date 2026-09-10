"""Read-only comparison and cost accounting for an unmodified live scorecard."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(), parse_float=Decimal)


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, default=str, sort_keys=True) + '\n')


def total(values):
    return sum((Decimal(str(value)) for value in values if value is not None), Decimal(0))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--scorecard', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--responses', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    helper_path=args.root/'docs/reports/evidence/registry/verification/72aa04a0/measurement-analysis/analyze_scorecards.py'
    spec=importlib.util.spec_from_file_location('retained_scorecard_observation', helper_path)
    helper=importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    candidate=read(args.scorecard)
    baselines={name:args.root/path for name,path in {
        '411':'docs/reports/evidence/411/live-measurement.json',
        '565':'docs/reports/evidence/565/live-measurement.json',
        'third':'docs/reports/evidence/registry/live-measurement-third.json',
    }.items()}
    comparisons={name:helper.compare(read(path), candidate) for name,path in baselines.items()}
    log_receipts,invoices,billing_lines,completed=helper.parse_log(args.log)
    rows=candidate['results']; receipts=[(row['id'], r) for row in rows for r in row['route_receipts']]
    def identity(case, r): return (case,r['created_at'],r['task'],r['model'],r['schema_name'])
    assert {identity(case,r) for case,r in receipts} == {identity(r['case_id'],r['receipt']) for r in log_receipts}
    assert {x['case']:(x['status'],x['failed_checks']) for x in completed} == {r['id']:(r['status'],r['failed_checks']) for r in rows}
    usage=[{'case_id':row['id'],**u} for row in rows for u in row['typed_outcome'].get('tool_usage',[])]
    assert len({(u['case_id'],u['call_id']) for u in usage})==len(usage)
    active=[u for u in usage if u['usage'].get('cache_status')!='hit']
    hits=[u for u in usage if u['usage'].get('cache_status')=='hit']
    priced=[u for u in active if u['usage'].get('cost_usd') is not None]
    invoice_overlap={i['case_id'] for i in invoices} & {u['case_id'] for u in priced}
    invoice_sum=total(i['reported_cost']['total_cost'] for i in invoices if i['case_id'] not in invoice_overlap)
    or_total=total(r.get('usage_cost_usd') for _,r in receipts)
    assert or_total==candidate['provider_usage']['reported_cost_usd']
    tool_total=total(u['usage']['cost_usd'] for u in priced)
    unknown=[{'case_id':case,**r} for case,r in receipts if r.get('usage_cost_usd') is None]
    responses=[json.loads(line,parse_float=Decimal) for line in args.responses.read_text().splitlines()]
    assert all(r['candidate_sha']==candidate['provenance']['candidate_sha'] for r in responses)
    assert {r['case_id'] for r in responses} <= {r['id'] for r in rows}
    cost={
        'currency':'USD',
        'openrouter_reported_usd':or_total,
        'openrouter_receipt_count':len(receipts),
        'openrouter_unpriced_records':unknown,
        'openrouter_unpriced_failure_modes':dict(Counter(r.get('failure_mode') for r in unknown)),
        'openrouter_local_zero_latency_unpriced_count':sum(r['latency_ms']==0 for r in unknown),
        'research_non_cached_reported_or_estimated_usd':tool_total,
        'research_unpriced_provider_reported_usd_without_overlap':invoice_sum,
        'overlapping_invoice_cases_not_added':sorted(invoice_overlap),
        'research_invoice_log_lines':billing_lines,
        'research_unique_unpriced_invoices':invoices,
        'cache_hit_usage_not_charged_again':hits,
        'tool_usage_as_recorded':usage,
        'accounted_reported_or_estimated_usd':or_total+tool_total+invoice_sum,
        'unknown_additional_cost':True if unknown or invoice_overlap or any(u['usage'].get('cost_usd') is None for u in active) else False,
        'basis':'Sum retained receipt costs and per-call non-cache-hit research usage; exclude cached packet prices. Separately add deduplicated unpriced provider invoices only without a potentially overlapping priced call. Missing charges remain unknown. Receipt rows are not unique provider requests.',
        'retained_openrouter_response_count':len(responses),
    }
    args.output.mkdir(parents=True,exist_ok=True)
    dump(args.output/'comparison.json',{'candidate':helper.summary(candidate),'comparisons':comparisons})
    dump(args.output/'cost-accounting.json',cost)
    files={'candidate':args.scorecard,'log':args.log,'responses':args.responses,'comparison_helper':helper_path,**baselines}
    dump(args.output/'provenance.json',{'candidate_provenance':candidate['provenance'],'inputs':{name:{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for name,path in files.items()}})
    print(json.dumps({'totals':candidate['totals'],'transitions':{name:{'passed_to_failed':r['passed_to_failed'],'failed_to_passed':r['failed_to_passed']} for name,r in comparisons.items()},'accounted_usd':cost['accounted_reported_or_estimated_usd'],'unknown_additional_cost':cost['unknown_additional_cost']},indent=2,default=str))

if __name__=='__main__': main()
