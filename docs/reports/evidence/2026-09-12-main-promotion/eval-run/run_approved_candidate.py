"""One founder-approved fresh candidate run; retain all prior cost and evidence."""
import hashlib
import json
import os
import signal
import subprocess
import time
from decimal import Decimal
from pathlib import Path

CONTROL = Path(__file__).parent
ORIGINAL = json.loads((CONTROL / 'status.json').read_text())
ENV = ORIGINAL['environment']
COMMAND = ORIGINAL['command']
TREE = Path('/private/tmp/argus-promotion-20260912-candidate-eval')
SHA = ORIGINAL['shas']['candidate']
LIMIT = Decimal('7.50')
EVENTS = CONTROL / 'events.jsonl'
STATUS = CONTROL / 'candidate-approved-retry-status.json'
SOURCE_PROOF = json.loads((CONTROL / 'environment-source-provenance.json').read_text())
assert ORIGINAL['state'] == 'spend_stop'
assert hashlib.sha256(Path(ENV['ARGUS_EVAL_ENV_FILE']).read_bytes()).hexdigest() == SOURCE_PROOF['sha256'], 'environment source changed'
assert hashlib.sha256((CONTROL / 'promotion_observer.py').read_bytes()).hexdigest() == ORIGINAL['observer_sha256'], 'observer changed'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=TREE, text=True).strip() == SHA
assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=TREE, text=True).strip()
assert all(not p.exists() and not p.is_symlink() for p in [TREE / '.env', TREE / 'web/.env.local'])
assert not list((TREE / 'temp/argus_eval_scorecards').glob('*.json')), 'candidate scorecard already exists; refuse another run'
for old in ORIGINAL['runs'].values():
    try:
        os.kill(old['pid'], 0)
    except ProcessLookupError:
        pass
    else:
        raise RuntimeError('prior process still exists; refuse overlap')

preflight_code = "import argus,json,sys; from pathlib import Path; from tests.evals.measurement_eval_harness import load_eval_cases; root=Path.cwd(); assert Path(argus.__file__).resolve().is_relative_to(root); assert all(Path(m.__file__).resolve().is_relative_to(root) for n,m in sys.modules.items() if (n=='argus' or n.startswith('argus.') or n.startswith('argus_display_contract')) and getattr(m,'__file__',None)); cases=load_eval_cases(); print(json.dumps({'argus_import_local':True,'all_imported_argus_modules_local':True,'cases':len(cases),'user_turns':sum(1+bool(c.followup_prompt) for c in cases)}))"
preflight = subprocess.run(['poetry', 'run', 'python', '-c', preflight_code], cwd=TREE,
                           env={k:v for k,v in ENV.items() if k != 'PYTEST_PLUGINS'}, capture_output=True, text=True)
if preflight.returncode:
    (CONTROL / 'approved-candidate-preflight.log').write_text(preflight.stderr)
    raise SystemExit(preflight.returncode)

initial_bytes = EVENTS.read_bytes()
initial_count = len(initial_bytes.splitlines())
status = {'state': 'preflight_passed', 'approval': 'Founder approved one fresh full candidate run with a 7.50 USD combined cap on tracked cost plus reserve; no further run if this guard stops.',
          'candidate_sha': SHA, 'baseline_sha': ORIGINAL['shas']['baseline'], 'combined_limit_usd': float(LIMIT),
          'environment': ENV, 'environment_identical_to_original_pair': True, 'environment_source_sha256': SOURCE_PROOF['sha256'],
          'observer_sha256': ORIGINAL['observer_sha256'], 'command': COMMAND, 'preflight': json.loads(preflight.stdout.strip().splitlines()[-1]),
          'initial_event_count': initial_count, 'prior_ledger_sha256': hashlib.sha256(initial_bytes).hexdigest(),
          'prior_tracked_cost_usd': ORIGINAL['reported_cost_usd'], 'prior_unpriced_non_skipped_receipts': ORIGINAL['unpriced_non_skipped_receipts'],
          'reserve_is_not_actual_spend': True}

def save():
    temporary = STATUS.with_suffix('.tmp')
    temporary.write_text(json.dumps(status, indent=2) + '\n')
    temporary.replace(STATUS)

def update_cost():
    total = Decimal('0')
    fresh = Decimal('0')
    unknown = 0
    cases = 0
    for index, line in enumerate(EVENTS.read_text().splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if index >= initial_count and event['kind'] == 'case_complete':
            cases += 1
        if event['kind'] != 'cost':
            continue
        if event['cost_usd'] is None:
            unknown += event.get('outcome') != 'skipped'
        else:
            cost = Decimal(str(event['cost_usd']))
            total += cost
            if index >= initial_count:
                fresh += cost
    reserve = Decimal('0.10') + Decimal('0.02') * unknown
    status.update(tracked_cost_usd=float(total), fresh_candidate_tracked_cost_usd=float(fresh),
                  unpriced_non_skipped_receipts=unknown, guard_reserve_usd=float(reserve),
                  guarded_total_usd=float(total + reserve), completed_cases=cases)
    return total + reserve >= LIMIT

update_cost()
save()
if '--preflight-only' in __import__('sys').argv:
    print(json.dumps({'state': status['state'], 'preflight': status['preflight'], 'environment_identical': True,
                      'tracked_cost_usd': status['tracked_cost_usd'], 'guard_reserve_usd': status['guard_reserve_usd']}))
    raise SystemExit(0)

# Exclusive marker makes a second launch impossible without a new human decision.
with os.fdopen(os.open(CONTROL / 'approved-candidate-run-once.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as lock:
    lock.write(str(time.time()) + '\n')
assert not update_cost(), 'already at approved cap'
with (CONTROL / 'candidate-full-approved.log').open('w') as log:
    child = subprocess.Popen(COMMAND, cwd=TREE, env=ENV, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True)
    status.update(state='running', pid=child.pid, started_at=time.time())
    save()
    while child.poll() is None:
        if update_cost():
            status['state'] = 'spend_stop'
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
            break
        save()
        time.sleep(0.2)
    status.update(exit_code=child.wait(), finished_at=time.time())
update_cost()
if status['state'] == 'running':
    status['state'] = 'completed'
status['environment_source_unchanged_after_run'] = hashlib.sha256(Path(ENV['ARGUS_EVAL_ENV_FILE']).read_bytes()).hexdigest() == SOURCE_PROOF['sha256']
if not status['environment_source_unchanged_after_run']:
    status['state'] = 'environment_check_failed'
save()
