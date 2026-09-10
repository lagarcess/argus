#!/usr/bin/env python3
"""Read frozen interleaved artifacts; preserve native grades and captured costs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys

EXPECTED_SHAS = {
    'baseline': '542fcfb2432e906663160d8cb874d955faeafd16',
    'candidate': '31b20baf7a036fdd9148bce8a90a838e076be201',
}
EXPECTED_COUNT = 56


def amount(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (InvalidOperation, ValueError):
        return None


def money(values):
    return str(sum((v for v in values if v is not None), Decimal(0)))


def snapshot(directory):
    files = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
        files[path.name] = {
            'raw': raw,
            'sha256': hashlib.sha256(raw).hexdigest(),
            'bytes': len(raw),
            'mtime_ns': after.st_mtime_ns,
            'stable': (before.st_size, before.st_mtime_ns)
            == (after.st_size, after.st_mtime_ns),
        }
    return files


def read_json(files, name):
    if name not in files:
        raise ValueError(f'Missing {name}')
    return json.loads(files[name]['raw'])


def research_usage(probe, label):
    typed = probe['results'][0].get('typed_outcome') or {}
    calls = typed.get('tool_usage') or []
    sidecar = probe.get('observed_final_research_sidecar') or {}
    sidecar_usage = sidecar.get('usage')
    rows, notes, seen = [], [], {}
    if calls:
        source = 'results[0].typed_outcome.tool_usage'
        for index, call in enumerate(calls):
            identity = call.get('call_id')
            usage = call.get('usage')
            if not identity or not isinstance(usage, dict):
                notes.append({'reason': 'unbound_or_malformed_tool_usage', 'index': index})
                continue
            if identity in seen:
                if usage != seen[identity]['usage']:
                    seen[identity]['conflicting_usage'] = True
                    notes.append({'reason': 'conflicting_usage_for_same_call', 'call_id': identity})
                else:
                    notes.append({'reason': 'duplicate_call_usage_ignored', 'call_id': identity})
                continue
            row = {'identity': identity, 'tool_name': call.get('tool_name'), 'usage': usage, 'source': source}
            seen[identity] = row
            rows.append(row)
        if sidecar_usage is not None:
            notes.append({
                'reason': 'sidecar_not_added_because_call_usage_is_primary',
                'matches_a_call': any(sidecar_usage == row['usage'] for row in rows),
                'sidecar_usage': sidecar_usage,
            })
    elif isinstance(sidecar_usage, dict):
        rows.append({'identity': 'legacy-final-sidecar', 'usage': sidecar_usage,
                     'source': 'observed_final_research_sidecar.usage'})
    for row in rows:
        usage = row['usage']
        cost = amount(usage.get('cost_usd'))
        row.update(label=label, reported_cost_usd=None if cost is None else str(cost))
        if usage.get('cache_status') == 'hit':
            row['accounting'] = 'cache_hit_excluded_from_new_spend'
            row['included_cost_usd'] = '0'
        elif row.get('conflicting_usage'):
            row['accounting'] = 'unknown_conflicting_usage'
            row['included_cost_usd'] = None
        elif cost is None:
            row['accounting'] = 'unknown_unreported_cost'
            row['included_cost_usd'] = None
        else:
            # The recorded cost remains real even if invocations is zero.
            row['accounting'] = 'recorded_noncache_cost'
            row['included_cost_usd'] = str(cost)
    return rows, notes


def native_grade(probe, label):
    result = probe['results'][0]
    typed = result.get('typed_outcome') or {}
    judge = result.get('prose_judge')
    integrity = []
    if isinstance(judge, dict):
        failed = judge.get('failed_criteria')
        if judge.get('pass') is False and failed == []:
            integrity.append('judge_failed_with_no_failed_criteria')
        if judge.get('pass') is True and isinstance(failed, list) and failed:
            integrity.append('judge_passed_with_failed_criteria')
    return {
        'grade_consistency_issues': integrity,
        'acceptance_grade_valid': not integrity,
        'label': label, 'status': result.get('status'),
        'failed_checks': result.get('failed_checks'),
        'expected_fail': result.get('expected_fail'),
        'infrastructure_errors': result.get('infrastructure_errors'),
        'prose_judge': None if judge is None else {
            key: judge.get(key) for key in ('pass', 'score', 'requested_criteria', 'failed_criteria', 'notes', 'rubric_version', 'selection_expectations')
        },
        'native_stage_outcomes': typed.get('stage_outcomes'),
        'native_acceptance_stage_outcomes': typed.get('acceptance_stage_outcomes'),
        'native_intent': typed.get('intent'),
        'native_primary_intent': typed.get('primary_intent'),
        'native_observation_fields': sorted(typed),
        'fixture_sha256': probe.get('provenance', {}).get('fixture_sha256'),
        'case_input_sha256': probe.get('case_input_sha256'),
        'elapsed_seconds': probe.get('elapsed_seconds'),
        'source': f'{label}.json#/results/0',
    }


def analyze(directory, review_notes=None):
    files = snapshot(directory)
    problems, unknown = [], []
    schedule = read_json(files, 'schedule.json')
    preflight = read_json(files, 'preflight.json')
    if not isinstance(schedule, list) or len(schedule) != EXPECTED_COUNT:
        problems.append(f'Schedule must contain exactly {EXPECTED_COUNT} entries')
    if not isinstance(schedule, list):
        schedule = []
    for arm, sha in EXPECTED_SHAS.items():
        if preflight.get(arm, {}).get('sha') != sha:
            problems.append(f'{arm} preflight SHA differs from frozen expected SHA')
        if preflight.get(arm, {}).get('clean') is not True:
            problems.append(f'{arm} preflight was not clean')
    labels, identities = set(), set()
    scheduled, valid, paired = [], {}, defaultdict(dict)
    ledger, by_probe_cost = {}, {}
    all_research, all_receipts = [], []
    for item in schedule:
        try:
            index, arm, rep, case = item['index'], item['arm'], item['repetition'], item['case']
            if arm not in EXPECTED_SHAS or rep not in (1, 2) or not isinstance(index, int):
                raise ValueError('invalid schedule fields')
            label = f'{index:02d}-{arm}-r{rep}'
        except (KeyError, TypeError, ValueError):
            problems.append('Malformed schedule item')
            continue
        if label in labels or (case, rep, arm) in identities:
            problems.append(f'Duplicate schedule identity: {label}')
        labels.add(label)
        identities.add((case, rep, arm))
        scheduled.append({'label': label, **item})
        output_name = label + '.json'
        try:
            probe = read_json(files, output_name)
            result = probe['results'][0]
            provenance = probe['provenance']
            expected_digest = preflight[arm]['inputs'][case]
            checks = {
                'label': probe.get('label') == label,
                'selected_case_ids': probe.get('selected_case_ids') == [case],
                'one_native_result': len(probe['results']) == 1 and result.get('id') == case,
                'native_status': isinstance(result.get('status'), str) and bool(result['status']),
                'native_checks': isinstance(result.get('failed_checks'), list),
                'frozen_sha': provenance.get('candidate_sha') == EXPECTED_SHAS[arm],
                'clean_worktree': provenance.get('worktree_clean') is True,
                'case_input': probe.get('case_input_sha256') == expected_digest,
                'cross_arm_case_input': expected_digest == preflight['candidate' if arm == 'baseline' else 'baseline']['inputs'][case],
                'live_mode': provenance.get('evaluation_mode') == 'live',
                'live_assets': provenance.get('asset_provider_mode') == 'live_provider',
                'live_market_data': provenance.get('market_data_provider_mode') == 'live_provider',
                'partial_probe_type': probe.get('artifact_type') == 'partial_interleaved_case_probe' and probe.get('is_full_suite_scorecard') is False,
            }
            failed = [key for key, value in checks.items() if not value]
            if failed:
                raise ValueError(', '.join(failed))
            valid[label] = probe
            paired[(case, rep)][arm] = native_grade(probe, label)
            paired[(case, rep)][arm]['human_review_note'] = (review_notes or {}).get(label)
        except (ValueError, KeyError, TypeError, IndexError) as exc:
            problems.append(f'{output_name}: {exc}')
            probe = None
        capture_name = label + '.responses.jsonl'
        captured_ids, capture_rows = set(), 0
        if capture_name not in files:
            unknown.append({'label': label, 'reason': 'missing_capture_file'})
        else:
            for line_number, line in enumerate(files[capture_name]['raw'].splitlines(), 1):
                if not line.strip():
                    continue
                capture_rows += 1
                location = f'{capture_name}:{line_number}'
                try:
                    captured = json.loads(line)
                    if not isinstance(captured, dict) or not isinstance(captured.get('response'), dict):
                        raise ValueError('malformed_capture_response')
                    response = captured['response']
                    if not isinstance(response.get('usage') or {}, dict):
                        raise ValueError('malformed_capture_usage')
                    identity = response.get('id')
                    if not identity or not isinstance(identity, str):
                        raise ValueError('missing_provider_response_id')
                    if captured.get('candidate_sha') != EXPECTED_SHAS[arm] or captured.get('label') != label or captured.get('case_id') != case:
                        raise ValueError('capture_provenance_mismatch')
                    cost = amount((response.get('usage') or {}).get('cost'))
                    entry = ledger.setdefault(identity, {'id': identity, 'cost_values': set(), 'locations': [], 'labels': set(), 'arms': set(), 'http_statuses': set(), 'model': response.get('model'), 'schema_names': set()})
                    if cost is not None:
                        entry['cost_values'].add(cost)
                    else:
                        unknown.append({'label': label, 'reason': 'captured_response_cost_missing_or_invalid', 'source': location, 'response_id': identity})
                    entry['locations'].append(location)
                    entry['labels'].add(label)
                    entry['arms'].add(arm)
                    entry['http_statuses'].add(captured.get('http_status'))
                    entry['schema_names'].add(captured.get('schema_name'))
                    captured_ids.add(identity)
                except (ValueError, KeyError, TypeError) as exc:
                    unknown.append({'label': label, 'reason': str(exc), 'source': location})
        receipts = [] if probe is None else probe['results'][0].get('route_receipts', [])
        for index, receipt in enumerate(receipts):
            all_receipts.append({'label': label, 'arm': arm, 'index': index, **receipt})
            if receipt.get('outcome') != 'skipped' and amount(receipt.get('usage_cost_usd')) is None:
                unknown.append({'label': label, 'reason': 'unpriced_route_receipt_without_response_id_join', 'receipt_index': index, 'note': 'May already be priced in captured responses; not an amount to add.'})
            if 'timeout' in str(receipt.get('failure_mode') or '').casefold():
                unknown.append({'label': label, 'reason': 'timed_out_request_cost_unknown', 'receipt_index': index, 'model': receipt.get('model'), 'schema_name': receipt.get('schema_name')})
        attempted_receipts = sum(row.get('outcome') != 'skipped' for row in receipts)
        if attempted_receipts > len(captured_ids):
            unknown.append({'label': label, 'reason': 'fewer_unique_captured_responses_than_attempted_route_receipts', 'minimum_unmatched_count': attempted_receipts - len(captured_ids)})
        research, research_notes = ([], []) if probe is None else research_usage(probe, label)
        for row in research:
            row['arm'] = arm
            if row['included_cost_usd'] is None:
                unknown.append({'label': label, 'reason': row['accounting'], 'research_identity': row['identity']})
        for note in research_notes:
            if note.get('matches_a_call') is False or note['reason'] in {'unbound_or_malformed_tool_usage', 'conflicting_usage_for_same_call'}:
                unknown.append({'label': label, 'reason': 'research_usage_identity_or_completeness_unresolved', 'detail': note})
        all_research.extend(research)
        by_probe_cost[label] = {
            'arm': arm, 'case': case, 'repetition': rep,
            'captured_response_ids': sorted(captured_ids), 'capture_rows': capture_rows,
            'route_receipt_known_cost_usd': money(amount(row.get('usage_cost_usd')) for row in receipts),
            'route_receipt_count': len(receipts),
            'route_receipt_cost_missing_count': sum(amount(row.get('usage_cost_usd')) is None for row in receipts),
            'reported_provider_usage': None if probe is None else probe.get('provider_usage'),
            'research_usage': research, 'research_accounting_notes': research_notes,
            'research_known_new_spend_usd': money(amount(row['included_cost_usd']) for row in research),
        }
    if {row['index'] for row in scheduled} != set(range(1, EXPECTED_COUNT + 1)):
        problems.append('Schedule indices are not exactly 1..56')
    cases = {row['case'] for row in scheduled}
    if len(cases) != 14 or any((case, rep, arm) not in identities for case in cases for rep in (1, 2) for arm in EXPECTED_SHAS):
        problems.append('Schedule is not 14 cases x 2 repetitions x 2 arms')
    serial_ledger = []
    for identity, entry in ledger.items():
        costs = entry.pop('cost_values')
        entry['known_cost_usd'] = str(next(iter(costs))) if len(costs) == 1 else None
        if len(costs) > 1:
            unknown.append({'reason': 'conflicting_costs_for_provider_response_id', 'response_id': identity, 'values': sorted(map(str, costs))})
        if len(entry['labels']) > 1:
            problems.append(f'Provider response ID is shared across scheduled probes: {identity}')
        for field in ('labels', 'arms', 'http_statuses', 'schema_names'):
            entry[field] = sorted(entry[field], key=lambda value: str(value))
        serial_ledger.append(entry)
    ledger_by_id = {entry['id']: entry for entry in serial_ledger}
    for label, costs in by_probe_cost.items():
        costs['captured_openrouter_known_cost_usd'] = money(amount(ledger_by_id[identity]['known_cost_usd']) for identity in costs['captured_response_ids'])
        costs['known_paid_lower_bound_usd'] = money([amount(costs['captured_openrouter_known_cost_usd']), amount(costs['research_known_new_spend_usd'])])
        costs['captured_minus_receipt_known_cost_usd'] = str(Decimal(costs['captured_openrouter_known_cost_usd']) - Decimal(costs['route_receipt_known_cost_usd']))
    observed_files = {path.name for path in directory.iterdir() if path.is_file()}
    if observed_files != set(files):
        problems.append('Input directory changed during analysis; take a new snapshot')
    for name, meta in files.items():
        current = (directory / name).stat()
        if not meta['stable'] or (current.st_size, current.st_mtime_ns) != (meta['bytes'], meta['mtime_ns']):
            problems.append(f'Input file changed during analysis: {name}')
    comparisons = []
    for case in sorted(cases):
        for rep in (1, 2):
            arms = paired[(case, rep)]
            both = len(arms) == 2
            baseline, candidate = arms.get('baseline', {}), arms.get('candidate', {})
            comparisons.append({
                'case': case, 'repetition': rep, 'arms': arms,
                'pair_complete': both,
                'pair_acceptance_grade_valid': all(row['acceptance_grade_valid'] for row in arms.values()) if both else None,
                'native_status_equal': baseline.get('status') == candidate.get('status') if both else None,
                'same_input_sha256': baseline.get('case_input_sha256') == candidate.get('case_input_sha256') if both else None,
                'same_fixture_sha256': baseline.get('fixture_sha256') == candidate.get('fixture_sha256') if both else None,
                'native_failed_checks_equal': baseline.get('failed_checks') == candidate.get('failed_checks') if both else None,
                'native_judge_criteria_equal': (baseline.get('prose_judge') or {}).get('requested_criteria') == (candidate.get('prose_judge') or {}).get('requested_criteria') if both else None,
                'grading_note': 'Native arm grades only; no common regrade. Full fixture hashes and observation fields can differ despite identical case inputs.',
            })
    complete = len(valid) == EXPECTED_COUNT and not problems
    invalid_grades = [
        {'label': grade['label'], 'native_status': grade['status'], 'issues': grade['grade_consistency_issues']}
        for arms in paired.values() for grade in arms.values() if not grade['acceptance_grade_valid']
    ]
    totals = {}
    for arm in (*EXPECTED_SHAS, 'all'):
        providers = [row for row in serial_ledger if arm == 'all' or row['arms'] == [arm]]
        research = [row for row in all_research if arm == 'all' or row['arm'] == arm]
        receipts = [row for row in all_receipts if arm == 'all' or row['arm'] == arm]
        provider_cost = money(amount(row['known_cost_usd']) for row in providers)
        research_cost = money(amount(row['included_cost_usd']) for row in research)
        totals[arm] = {
            'captured_openrouter_known_cost_usd': provider_cost,
            'unique_captured_response_count': len(providers),
            'research_known_new_spend_usd': research_cost,
            'known_paid_lower_bound_usd': money([amount(provider_cost), amount(research_cost)]),
            'route_receipt_known_cost_usd_separate_not_added': money(amount(row.get('usage_cost_usd')) for row in receipts),
        }
    return {
        'scope': 'complete_selected_56_probe_schedule' if complete else 'PARTIAL_NOT_TERMINAL',
        'is_full_suite_scorecard': False,
        'acceptance_grade_integrity': {'valid': not invalid_grades, 'invalid_native_grades': invalid_grades, 'note': 'Invalidity flags preserve every native status and do not regrade outcomes.'},
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'readiness': {'terminal_summary_allowed': complete, 'expected_outputs': EXPECTED_COUNT, 'valid_outputs': len(valid), 'problems': problems, 'missing_outputs': [row['label'] + '.json' for row in scheduled if row['label'] + '.json' not in files]},
        'provenance': {'expected_shas': EXPECTED_SHAS, 'preflight': preflight, 'schedule': schedule, 'input_directory': str(directory), 'source_manifest': {name: {key: value for key, value in row.items() if key != 'raw'} for name, row in files.items()}},
        'comparison': comparisons,
        'native_status_counts': {arm: dict(Counter(probe['results'][0]['status'] for label, probe in valid.items() if by_probe_cost[label]['arm'] == arm)) for arm in EXPECTED_SHAS},
        'cost_accounting': {
            'currency': 'USD', 'amount_encoding': 'decimal strings',
            'totals': totals, 'per_probe': by_probe_cost,
            'captured_response_ledger': serial_ledger,
            'unresolved_cost_evidence': unknown,
            'additional_cost_unknown': bool(unknown) or not complete,
            'method': 'Sum usage.cost once per captured provider response.id, including schema-rejected completed responses and captured judges. Add recorded non-cache research usage once per call; prefer typed tool_usage over duplicate final sidecar. Route-receipt sums overlap captured costs and are never added. No prices inferred from invocations or timeout status.',
            'limitations': ['A known subtotal is a lower bound, not an invoice total.', 'Route receipts lack provider response IDs; unresolved coverage counts do not identify individual requests.', 'Missing/invalid captures and timed-out requests retain unknown additional cost.', 'Only exported research usage is observable; null cost is not zero.', 'Native grades and publication facts are copied, never recalculated.'],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('/private/tmp/registry-interleaved-fourth-repairs'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--review-notes', type=Path, default=Path(__file__).with_name('review-notes.json'))
    parser.add_argument('--partial', action='store_true', help='Permit explicitly partial diagnostics; never produce terminal summary')
    args = parser.parse_args()
    source, output = args.input.resolve(), args.output.resolve()
    if output == source or source in output.parents:
        parser.error('Output must be outside the raw input directory')
    try:
        notes_raw = args.review_notes.read_bytes() if args.review_notes.exists() else b'{}'
        report = analyze(source, review_notes=json.loads(notes_raw))
        report['provenance']['analysis_script_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        report['provenance']['review_notes'] = {'path': str(args.review_notes), 'sha256': hashlib.sha256(notes_raw).hexdigest(), 'annotations': json.loads(notes_raw)}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f'Analysis refused: {exc}', file=sys.stderr)
        return 2
    if not report['readiness']['terminal_summary_allowed'] and not args.partial:
        print(json.dumps({'scope': 'REFUSED_INCOMPLETE_TERMINAL_SUMMARY', **report['readiness']}, indent=2))
        return 2
    output.mkdir(parents=True, exist_ok=False)
    if args.partial:
        report['scope'] = 'PARTIAL_DIAGNOSTIC_NOT_TERMINAL'
    (output / 'analysis.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    for key in ('comparison', 'cost_accounting', 'provenance', 'readiness'):
        (output / (key.replace('_', '-') + '.json')).write_text(json.dumps({'scope': report['scope'], key: report[key]}, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'scope': report['scope'], 'valid_outputs': report['readiness']['valid_outputs'], 'output': str(output)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
