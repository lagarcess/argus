"""Preserve native scorecards and compare outcomes without rewriting measurements."""
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from dotenv import dotenv_values

control = Path(__file__).parent
output = Path('/Users/garces/.codex/worktrees/eca1/private-alpha-next/docs/reports/evidence/2026-09-12-main-promotion')
status = json.loads((control / 'candidate-approved-retry-status.json').read_text())
original = json.loads((control / 'status.json').read_text())
candidate_cases = status['preflight']['cases']
candidate_turns = status['preflight']['user_turns']
baseline_cases = original['runs']['baseline']['preflight']['cases']
baseline_turns = original['runs']['baseline']['preflight']['user_turns']
baseline_cost = original['cost_by_side']['baseline']
assert status['state'] == 'completed', 'Fresh candidate run is not complete'
assert status['environment_source_unchanged_after_run'] is True
assert status['completed_cases'] == candidate_cases
paths = list(Path('/private/tmp/argus-promotion-20260912-candidate-eval/temp/argus_eval_scorecards').glob('*.json'))
assert len(paths) == 1, 'Expected one native candidate scorecard'
candidate_bytes = paths[0].read_bytes()
candidate = json.loads(candidate_bytes)
baseline_path = control / 'baseline-eval-scorecard-ee9c3491.json'
baseline_bytes = baseline_path.read_bytes()
baseline = json.loads(baseline_bytes)
events = [json.loads(line) for line in (control / 'events.jsonl').read_text().splitlines()]
event_end = next(index + 1 for index,event in enumerate(events)
                 if index >= status['initial_event_count'] and event['kind'] == 'observer_end')
fresh_costs = {}
for event in events[status['initial_event_count']:event_end]:
    if event['kind'] == 'cost' and event['cost_usd'] is not None:
        provider = event['provider']
        fresh_costs[provider] = fresh_costs.get(provider, Decimal('0')) + Decimal(str(event['cost_usd']))
assert abs(float(sum(fresh_costs.values())) - status['fresh_candidate_tracked_cost_usd']) < 1e-9
assert abs(float(fresh_costs['openrouter']) - candidate['provider_usage']['reported_cost_usd']) < 1e-9, 'Observer and native OpenRouter cost totals disagree'
for scorecard, sha, count in [(candidate, status['candidate_sha'], candidate_cases), (baseline, status['baseline_sha'], baseline_cases)]:
    provenance = scorecard['provenance']
    assert scorecard['schema_version'] == 2
    assert provenance['candidate_sha'] == sha
    assert provenance['evaluation_mode'] == 'live'
    assert provenance['market_data_provider_mode'] == provenance['asset_provider_mode'] == 'live_provider'
    assert provenance['worktree_clean'] is True
    assert provenance['python_version'] == baseline['provenance']['python_version']
    assert provenance['live_market_data_probe']['adjustment_reason'] == 'calendar_alignment'
    assert [row['id'] for row in scorecard['results']] == provenance['fixture_case_ids']
    assert len(scorecard['results']) == count
    assert sum(scorecard['totals'].values()) == count

source = Path(status['environment']['ARGUS_EVAL_ENV_FILE'])
assert hashlib.sha256(source.read_bytes()).hexdigest() == status['environment_source_sha256']
secrets = [v for k,v in dotenv_values(source).items() if v and len(v) >= 8 and re.search('KEY|TOKEN|PASSWORD|SECRET|DATABASE|POOLER', k)]
assert not any(secret.encode() in candidate_bytes for secret in secrets), 'Native candidate artifact contains a secret; do not publish'
target = output / 'candidate-eval-scorecard-df7aee12.json'
assert not target.exists() or target.read_bytes() == candidate_bytes, 'Refuse to replace a different native scorecard'
target.write_bytes(candidate_bytes)
assert (output / baseline_path.name).read_bytes() == baseline_bytes

by_baseline = {row['id']:row for row in baseline['results']}
by_candidate = {row['id']:row for row in candidate['results']}
differences = []
for case_id in sorted(set(by_baseline) | set(by_candidate)):
    left, right = by_baseline.get(case_id), by_candidate.get(case_id)
    if left is None or right is None or left['status'] != right['status'] or right['status'] != 'passed':
        differences.append({'case_id':case_id, 'baseline_status':left['status'] if left else 'not_in_baseline',
            'candidate_status':right['status'] if right else 'not_in_candidate',
            'baseline_failed_checks':left['failed_checks'] if left else [],
            'candidate_failed_checks':right['failed_checks'] if right else [],
            'candidate_infrastructure_errors':right['infrastructure_errors'] if right else []})
nonpasses = [row for row in candidate['results'] if row['status'] != 'passed']
comparison = {'status':'pass' if not nonpasses else 'requires_case_disposition',
    'baseline_sha':status['baseline_sha'], 'candidate_sha':status['candidate_sha'],
    'candidate_native_sha256':hashlib.sha256(candidate_bytes).hexdigest(),
    'baseline_native_sha256':hashlib.sha256(baseline_bytes).hexdigest(),
    'baseline_totals':baseline['totals'], 'candidate_totals':candidate['totals'],
    'fixture_relationship':json.loads((control / 'fixture-comparison.json').read_text()),
    'case_differences':differences, 'full_environment_identical':True,
    'prior_partial_candidate_excluded_from_quality_comparison':True,
    'prior_partial_candidate_cost_included':True,
    'guarded_total_usd':status['guarded_total_usd'], 'tracked_cost_usd':status['tracked_cost_usd'],
    'guard_reserve_usd':status['guard_reserve_usd'], 'reserve_is_not_actual_spend':True,
    'combined_cap_usd':status['combined_limit_usd'], 'fresh_candidate_tracked_cost_usd':status['fresh_candidate_tracked_cost_usd'],
    'fresh_candidate_cost_by_provider':{key:float(value) for key,value in fresh_costs.items()},
    'fresh_full_run_event_boundary':{'start':status['initial_event_count'],'end_exclusive':event_end},
    'openrouter_observer_matches_native_scorecard':True,
    'candidate_user_turns':candidate_turns, 'baseline_user_turns':baseline_turns,
    'fresh_candidate_tracked_cost_per_user_turn_usd':status['fresh_candidate_tracked_cost_usd']/candidate_turns,
    'baseline_tracked_cost_per_user_turn_usd':baseline_cost/baseline_turns,
    'candidate_only_failed_case_ids':[row['id'] for row in nonpasses if by_baseline.get(row['id'],{}).get('status') != 'failed']}
(output / 'approved-eval-comparison.json').write_text(json.dumps(comparison, indent=2)+'\n')
for name in ['candidate-approved-retry-status.json', 'run_approved_candidate.py', 'candidate-full-approved.log']:
    text = (control / name).read_text()
    for secret in secrets:
        text = text.replace(secret, '<redacted>')
    (output / 'eval-run' / name).write_text('\n'.join(line.rstrip() for line in text.splitlines())+'\n')
(output / 'eval-run/all-attempt-events.jsonl').write_bytes((control / 'events.jsonl').read_bytes())
print(json.dumps({key:comparison[key] for key in ['status','baseline_totals','candidate_totals','tracked_cost_usd','guard_reserve_usd','guarded_total_usd','candidate_only_failed_case_ids']}))
