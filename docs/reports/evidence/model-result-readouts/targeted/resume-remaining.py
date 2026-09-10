"""Continue only three unattempted visits of the original 48-task measurement.

Default is a free preflight. --live is reserved for the captain's authorized run.
The stopped visit is immutable evidence, never retried or converted to a pass.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/Users/garces/.codex/worktrees/7c2d/private-alpha-next')
ORIGINAL = Path('/private/tmp/model-result-readouts-live.json')
ORIGINAL_SHA = 'b54a293836278d688def0d6d9fbdcc414db451db63ac129f5c388e527c19c2ff'
PRICING = Path('/private/tmp/model-result-readouts-refreshed-prices.json')
PRICING_SHA = '6f797f530981fb6f9ea6b5fdcc901c740497f9aec3505c10ef5cd1df46ca4d81'
FIXTURES = ROOT / 'docs/reports/evidence/model-result-readouts/recorded-fixtures.json'
PRESERVED = Path('/private/tmp/model-result-readouts-live-before-resume.json')
OUTPUT = Path('/private/tmp/model-result-readouts-live-completed.json')
EXPECTED_SHAS = {
    'baseline': 'd0884c3de81f8c53d454ac4f68f461d3b5dd77e3',
    'candidate': '847cdd5e54e9e6256483ee2987a3f59bb79b8ebb',
}
EXPECTED_FIXTURE_SHA = 'b255b3b18050a6c7ca7b39fd99645ca3297a4b50a373bf109895ea4fe9793851'
CAP = 3.5

sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env', override=False)  # Read only, same original parent setup.
from tests.evals.result_readout_eval import (  # noqa: E402
    MAX_ATTEMPTS,
    MAX_INPUT_BYTES,
    CostGuard,
    build_schedule,
    checkout_provenance,
    estimate_ceiling,
    invoke_probe,
    load_fixture_set,
    measurement_can_continue,
    sha256,
)
from tests.evals.result_readout_probe import cost_accounting  # noqa: E402


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


def no_measurement_processes() -> None:
    result = subprocess.run(
        ['ps', '-axo', 'pid=,ppid=,command='], capture_output=True, text=True, check=True
    )
    rows = {}
    for line in result.stdout.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) == 3:
            rows[int(fields[0])] = (int(fields[1]), fields[2])
    ancestors = set()
    pid = os.getpid()
    while pid in rows and pid not in ancestors:
        ancestors.add(pid)
        pid = rows[pid][0]
    markers = (
        'result_readout_probe.py', 'result_readout_eval.py',
        'tests.evals.result_readout_eval', Path(__file__).name,
    )
    active = [pid for pid, (_, command) in rows.items()
              if pid not in ancestors and any(marker in command for marker in markers)]
    require(not active, 'measurement_process_still_running')


def stable_inputs(original: dict) -> None:
    require(sha256(ORIGINAL.read_bytes()) == ORIGINAL_SHA, 'original_report_changed')
    require(sha256(PRICING.read_bytes()) == PRICING_SHA, 'pricing_changed')
    for variant, recorded in original['checkouts'].items():
        current = checkout_provenance(Path(recorded['checkout']), require_clean=True)
        require(current == recorded, 'checkout_provenance_changed')
        require(current['commit'] == EXPECTED_SHAS[variant], 'unexpected_source_sha')
    for name, report_key in (('result_readout_eval.py', 'runner_sha256'),
                             ('result_readout_probe.py', 'probe_sha256')):
        require(sha256((ROOT / 'tests/evals' / name).read_bytes()) == original[report_key],
                'measurement_source_changed')
    fixtures = load_fixture_set(FIXTURES, live=True)
    require(fixtures['fixture_sha256'] == original['fixture_sha256'] == EXPECTED_FIXTURE_SHA,
            'fixture_changed')
    require({case['id']: case['source'] for case in fixtures['cases']} == original['fixture_sources'],
            'fixture_provenance_changed')
    no_measurement_processes()


def verify_original(original: dict, rates: dict) -> tuple[list[dict], dict]:
    require(original['schema_version'] == 'targeted_readout_scorecard/v1', 'wrong_schema')
    require(original['evaluation_mode'] == 'live_targeted', 'not_live_original')
    require(original['budget']['approved_usd'] == CAP, 'approved_cap_changed')
    require(original['budget']['max_input_bytes'] == MAX_INPUT_BYTES and
            original['budget']['max_attempts_per_task'] == MAX_ATTEMPTS, 'bounds_changed')
    fixtures = load_fixture_set(FIXTURES, live=True)
    cases = {case['id']: case for case in fixtures['cases']}
    schedule = build_schedule(list(cases))
    rows = original['results']
    require(len(rows) == 21 and len(schedule) == 24, 'exact_21_visit_prefix_required')
    for index, row in enumerate(rows):
        require({key: row[key] for key in schedule[index]} == schedule[index],
                'schedule_prefix_changed')
        if index < 20:
            require(measurement_can_continue(row), 'earlier_visit_also_stopped')
        guard = CostGuard(budget_usd=CAP, rates=rates)
        for receipt in row['requests']:
            require(receipt['attempt_id'] == guard.attempts + 1, 'attempt_order_changed')
            require(0 < receipt['payload_bytes'] <= MAX_INPUT_BYTES, 'invalid_recorded_payload_bound')
            reserved = guard.reserve(
                {'model': receipt['model'], 'max_tokens': receipt['max_output_tokens'], 'messages': []},
                task=receipt['task'],
            )
            require(math.isclose(reserved, receipt['reserved_usd'], abs_tol=1e-12),
                    'recorded_reservation_price_mismatch')
        recomputed = cost_accounting(guard=guard, observations=copy.deepcopy(row))
        for key, value in recomputed.items():
            require(value == row[key] or (
                isinstance(value, float) and math.isclose(value, row[key], abs_tol=1e-12)
            ), 'original_accounting_mismatch')
    last = rows[-1]
    require(last['guard_failures'] == ['provider_worker_unsettled'], 'different_stop_reason')
    require(last['all_attempts_reserved'] is True and last['requires_process_exit'] is True
            and last['provider_worker_settled'] is False and last['http_closed'] is True
            and last['stop_requested'] is True, 'unsafe_previous_stop')
    require(sum(receipt['outcome'] == 'pending' for receipt in last['requests']) == 1,
            'unexpected_pending_attempt_count')
    require(math.isclose(sum(row['reserved_usd'] for row in rows),
                         original['budget']['reserved_usd'], abs_tol=1e-12),
            'original_reserved_total_mismatch')
    return schedule[21:], cases


def aggregate(report: dict) -> None:
    for key in ('reserved_usd', 'observed_cost_usd', 'unknown_cost_reserved_usd',
                'accounted_upper_bound_usd'):
        report['budget'][key] = sum(row[key] for row in report['results'])
    counts = [row['unknown_cost_attempts'] for row in report['results']]
    report['budget']['unknown_cost_attempts'] = None if None in counts else sum(counts)
    report['budget']['cost_complete'] = all(row['cost_complete'] for row in report['results'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    raw = ORIGINAL.read_bytes()
    original = json.loads(raw)
    stable_inputs(original)
    rates = json.loads(PRICING.read_text())['models']
    remaining, cases = verify_original(original, rates)
    require(not OUTPUT.exists() and not PRESERVED.exists(), 'continuation_already_started')
    preflight = []
    for row in remaining:
        probe = invoke_probe(
            python=sys.executable,
            checkout=Path(original['checkouts'][row['variant']]['checkout']),
            case=cases[row['case_id']], language=row['language'], live=False,
            budget_usd=0, rates=rates,
        )
        expected = next(item['configuration'] for item in original['results']
                        if item['variant'] == row['variant'])
        actual = dict(probe['configuration'])
        actual['llm_mode'] = 'live_provider'
        require(actual == expected, 'runtime_configuration_changed')
        require(probe['http_attempts'] == 0 and not probe['guard_failures'], 'preflight_not_free')
        require(all(p['bytes'] <= MAX_INPUT_BYTES for p in probe['preflight_payloads']),
                'preflight_payload_exceeds_bound')
        preflight.append(probe)
    ceiling = estimate_ceiling(preflight, rates)
    reserved = sum(row['reserved_usd'] for row in original['results'])
    require(ceiling <= CAP - reserved, 'remaining_cap_insufficient')
    stable_inputs(original)
    summary = {
        'live': args.live, 'original_sha256': ORIGINAL_SHA,
        'retained_visits': 21, 'unattempted_visits': remaining,
        'remaining_task_completions': 6, 'prior_reserved_usd': reserved,
        'remaining_cap_usd': CAP - reserved, 'remaining_worst_case_usd': ceiling,
        'free_preflight_http_attempts': 0,
        'max_preflight_payload_bytes': max(p['bytes'] for r in preflight for p in r['preflight_payloads']),
        'same_runtime_configuration': True, 'owned_measurement_processes': [],
    }
    if not args.live:
        print(json.dumps(summary, indent=2))
        return
    with PRESERVED.open('xb') as file:
        file.write(raw)
    PRESERVED.chmod(0o444)
    report = copy.deepcopy(original)
    report['execution_segments'] = [
        {'kind': 'original_attempts', 'visits': 21, 'source': str(PRESERVED),
         'sha256': ORIGINAL_SHA, 'terminal_stop': 'provider_worker_unsettled'},
        {'kind': 'authorized_unattempted_continuation', 'scheduled_visits': remaining,
         'started_at': datetime.now(timezone.utc).isoformat(), 'completed_visits': 0,
         'script_sha256': sha256(Path(__file__).read_bytes()), 'pricing_sha256': PRICING_SHA,
         'note': 'Only the original schedule tail. The stopped baseline RSI visit and its fully reserved pending attempt remain unchanged. No retry, new quality pass, or fingerprint authority.'},
    ]
    report['continuation_preflight'] = summary
    with OUTPUT.open('x') as file:
        file.write(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    for row, dry in zip(remaining, preflight, strict=False):
        stable_inputs(original)
        probe = invoke_probe(
            python=sys.executable,
            checkout=Path(original['checkouts'][row['variant']]['checkout']),
            case=cases[row['case_id']], language=row['language'], live=True,
            budget_usd=CAP - sum(item['reserved_usd'] for item in report['results']),
            rates=rates, preflight=dry,
        )
        role = next(item['display_evidence_role'] for item in original['results']
                    if item['variant'] == row['variant'])
        report['results'].append({**row, **probe, 'display_evidence_role': role})
        require(report['results'][:21] == original['results'], 'original_rows_changed')
        aggregate(report)
        segment = report['execution_segments'][-1]
        segment['completed_visits'] += 1
        segment['status'] = 'in_progress' if measurement_can_continue(probe) else 'stopped_again'
        segment['updated_at'] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
        require(measurement_can_continue(probe), 'continuation_stopped_preserved_evidence')
    report['execution_segments'][-1]['status'] = 'all_original_schedule_visits_attempted'
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'output': str(OUTPUT), 'original_preserved': str(PRESERVED),
                      'visits': len(report['results']), 'budget': report['budget']}))


if __name__ == '__main__':
    main()
