"""Preserve completed native attempts and summarize rates without dropping failures."""
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime, timezone
from dotenv import dotenv_values

control = Path(__file__).parent
source = control / 'targeted-ab'
root = Path('/Users/garces/.codex/worktrees/eca1/private-alpha-next')
evidence = root / 'docs/reports/evidence/2026-09-12-main-promotion'
target = evidence / 'targeted-ab'
state = json.loads((source / 'status.json').read_text())
assert state['state'] not in {'running', 'preflight'}, 'Do not finalize a live measurement'
target.mkdir(exist_ok=True)
secrets = [value for key,value in dotenv_values('/Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next/.env').items()
           if value and len(value) >= 8 and re.search('KEY|TOKEN|PASSWORD|SECRET|DATABASE|POOLER', key)]
for path in [*source.glob('*.json'), *source.glob('*.log'), control / 'targeted-ab-preflight.json',
             control / 'test_interleaved_ab.py', control / 'run_interleaved_ab.py', Path(__file__)]:
    raw = path.read_bytes()
    assert not any(value.encode() in raw for value in secrets), f'Secret in {path.name}'
    assert not re.search(rb'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',raw), f'JWT in {path.name}'
    if path.suffix == '.log': raw = ('\n'.join(line.rstrip() for line in raw.decode().splitlines()) + '\n').encode()
    (target / path.name).write_bytes(raw)
events = (control / 'events.jsonl').read_text().splitlines()
(target / 'events.jsonl').write_text('\n'.join(events[state['initial_event_count']:]) + '\n')
for side in ('baseline', 'candidate'):
    attempts = []
    for record in state['completed_attempts']:
        if record['side'] != side: continue
        path = source / record['artifact']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['artifact_sha256']
        attempts.append(json.loads(path.read_text()))
    if not attempts: continue
    provenance = attempts[0]['provenance']
    assert all(attempt['provenance'] == provenance for attempt in attempts)
    assert provenance['candidate_sha'] == state['shas'][side] and provenance['worktree_clean']
    assert all(attempt['targeted_case_sha256'] == attempts[0]['targeted_case_sha256'] for attempt in attempts)
    failed = sum(attempt['measurement']['failed'] for attempt in attempts)
    timeouts = sum(attempt['measurement']['research_timeout'] for attempt in attempts)
    assert failed == state['failures'][side] and timeouts == state['research_timeouts'][side]
    n = len(attempts)
    doc = {'schema_version': 1, 'scorecard_kind': 'live_targeted_interleaved_ab',
           'case_id': state['case_id'], 'side': side, 'provenance': provenance,
           'targeted_case_sha256': attempts[0]['targeted_case_sha256'],
           'native_case': attempts[0]['native_case'], 'environment_identical_to_completed_pair': True,
           'environment_source_sha256': state['environment_source_sha256'],
           'generated_at': datetime.now(timezone.utc).isoformat(),
           'paired_execution': {'order': state['order'], 'planned_rounds': 10,
               'completed_attempt_numbers': [attempt['attempt'] for attempt in attempts],
               'state': state['state']},
           'measurement': {'attempts': n, 'failed_count': failed, 'failed_rate': failed / n,
               'passed_count': n - failed, 'passed_rate': (n - failed) / n,
               'research_timeout_count': timeouts, 'research_timeout_rate': timeouts / n,
               'criterion': 'Any native non-pass or research timeout is a failed attempt. No attempt is discarded.',
               'fixture_comparison_note': 'Inputs are identical. Each build retains its committed typed expectations and prose rubric; production expects a future-performance limitation, candidate expects researched scenarios.'},
           'attempts': attempts}
    (evidence / f'targeted-ab-{side}.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
print(json.dumps({'state': state['state'], 'completed': len(state['completed_attempts']),
                  'failures': state['failures'], 'research_timeouts': state['research_timeouts'],
                  'tracked_cost_usd': state['tracked_cost_usd'], 'reserve_usd': state['guard_reserve_usd'],
                  'guarded_total_usd': state['guarded_total_usd']}))
