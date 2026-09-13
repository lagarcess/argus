"""Founder-authorized ten paired attempts with a spend guard and provider cooldown."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from decimal import Decimal

CONTROL = Path(__file__).parent
OUTPUT = CONTROL / 'sharing-off-targeted-ab'
OUTPUT.mkdir(mode=0o700, exist_ok=True)
ORIGINAL = json.loads((CONTROL / 'status.json').read_text())
FULL = json.loads((CONTROL / 'sharing-off-full-candidate-status.json').read_text())
assert FULL['state'] == 'completed' and FULL['completed_cases'] == 71
assert json.loads((CONTROL / 'sharing-off-walk-complete.json').read_text())['new_blocking_p0_p1'] is False
ENV = ORIGINAL['environment']
CASE_ID = 'messy_spanish_future_performance_nvda_cruce_dorado'
CAP = Decimal('12.50')
SHAS = {'baseline': ORIGINAL['shas']['baseline'], 'candidate':'4fd587bf24ce39b794c2228d61f94693826d0da2'}
TREES = {'baseline':Path('/private/tmp/argus-promotion-20260912-baseline-eval'),'candidate':Path('/private/tmp/argus-promotion-20260913-sharing-off-candidate-eval')}
STATE = {'state': 'preflight', 'case_id': CASE_ID, 'combined_cap_usd': float(CAP),
         'shas': SHAS, 'order': 'baseline_then_candidate_per_round', 'planned_attempts_per_side': 10,
         'completed_attempts': [], 'failures': {'baseline': 0, 'candidate': 0},
         'research_timeouts': {'baseline': 0, 'candidate': 0},
         'reserve_is_not_spend': True, 'environment_identical_to_completed_pair': True,
         'environment_source_sha256': FULL['environment_source_sha256'],
         'started_at_epoch': time.time(), 'failure_gap_stop_applies':False, 'http_status_capture_enabled':True, 'cooldowns':[], 'candidate_research_delivery_failure_streak':0}

HTTP_OBSERVER_SHA = hashlib.sha256((CONTROL / 'promotion_http_observer.py').read_bytes()).hexdigest()
STATE['http_observer_sha256'] = HTTP_OBSERVER_SHA

def verify():
    assert hashlib.sha256((CONTROL / 'promotion_http_observer.py').read_bytes()).hexdigest() == HTTP_OBSERVER_SHA
    assert hashlib.sha256(Path(ENV['ARGUS_EVAL_ENV_FILE']).read_bytes()).hexdigest() == FULL['environment_source_sha256']
    assert hashlib.sha256((CONTROL / 'promotion_observer.py').read_bytes()).hexdigest() == ORIGINAL['observer_sha256']
    for side, tree in TREES.items():
        assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=tree, text=True).strip() == SHAS[side]
        assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=tree, text=True).strip()
        assert not (tree / '.env').exists() and not (tree / 'web/.env.local').exists()

def costs():
    total, unknown = Decimal('0'), 0
    for line in (CONTROL / 'events.jsonl').read_text().splitlines():
        try: event = json.loads(line)
        except ValueError: continue
        if event['kind'] != 'cost': continue
        if event['cost_usd'] is None: unknown += event.get('outcome') != 'skipped'
        else: total += Decimal(str(event['cost_usd']))
    reserve = Decimal('.10') + Decimal('.02') * unknown
    STATE.update(tracked_cost_usd=float(total), guard_reserve_usd=float(reserve),
                 guarded_total_usd=float(total + reserve), unpriced_non_skipped_receipts=unknown)
    return total + reserve

def save():
    costs()
    path = OUTPUT / 'status.json'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(STATE, indent=2) + '\n')
    tmp.replace(path)

def stop(reason):
    STATE.update(state=reason, finished_at_epoch=time.time())
    save()
    raise SystemExit(0)

for line in subprocess.check_output(['ps','-axo','command='],text=True).splitlines():
    assert not ('pytest ' in line and any(n in line for n in ('test_measurement_eval_live.py','test_interleaved_ab.py','test_sharing_off_interleaved_ab.py'))), 'another live eval process exists'
verify()
initial_guard = costs()
assert initial_guard < CAP
STATE['initial_tracked_cost_usd'] = STATE['tracked_cost_usd']
STATE['initial_guard_reserve_usd'] = STATE['guard_reserve_usd']
STATE['initial_guarded_total_usd'] = float(initial_guard)
STATE['initial_event_count'] = len((CONTROL / 'events.jsonl').read_text().splitlines())
with os.fdopen(os.open(OUTPUT / 'launch-once.lock', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as lock:
    lock.write(str(time.time()) + '\n')
save()
for attempt in range(1, 11):
    for side in ('baseline', 'candidate'):
        verify()
        if costs() >= CAP: stop('spend_stop')
        tree = TREES[side]
        command = ['poetry', 'run', 'pytest', '-c', str(tree / 'pyproject.toml'),
                   str(CONTROL / 'test_sharing_off_interleaved_ab.py') + f'::test_targeted_case[{attempt}]', '-q']
        event_start = len((CONTROL / 'events.jsonl').read_text().splitlines())
        with (OUTPUT / f'attempt-{attempt:02d}-{side}.log').open('x') as log:
            child = subprocess.Popen(command, cwd=tree, env=ENV, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            STATE.update(state='running', active_side=side, active_attempt=attempt,
                         active_pid=child.pid, active_command=command)
            save()
            while child.poll() is None:
                if costs() >= CAP:
                    os.killpg(child.pid, signal.SIGTERM)
                    try: child.wait(timeout=5)
                    except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL)
                    STATE['interrupted_exit_code'] = child.wait()
                    stop('spend_stop')
                save()
                time.sleep(.25)
            exit_code = child.wait()
        verify()
        path = OUTPUT / f'attempt-{attempt:02d}-{side}.json'
        if exit_code or not path.exists():
            STATE.update(runner_exit_code=exit_code, failed_log=str(OUTPUT / f'attempt-{attempt:02d}-{side}.log'))
            stop('measurement_runner_error')
        document = json.loads(path.read_text())
        assert document['side'] == side and document['attempt'] == attempt
        assert document['provenance']['candidate_sha'] == SHAS[side]
        STATE['failures'][side] += int(document['measurement']['failed'])
        STATE['research_timeouts'][side] += int(document['measurement']['research_timeout'])
        STATE['completed_attempts'].append({'side': side, 'attempt': attempt,
            'failed': document['measurement']['failed'], 'research_timeout': document['measurement']['research_timeout'],
            'native_status': document['result']['status'], 'event_start': event_start,
            'event_end_exclusive': len((CONTROL / 'events.jsonl').read_text().splitlines()),
            'artifact': path.name, 'artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        save()
    if attempt == 1:
        pair_guard_delta = costs() - initial_guard
        projected = initial_guard + pair_guard_delta * 10
        projection = {'basis': 'First two attempts: one deployed and one candidate. Extrapolate their tracked cost and reserve growth over ten pairs.',
            'initial_guarded_total_usd': float(initial_guard), 'first_pair_guarded_delta_usd': float(pair_guard_delta),
            'projected_combined_guarded_total_usd': float(projected), 'combined_cap_usd': float(CAP),
            'projection_within_cap': projected <= CAP,
            'checked_before_attempt_three': True, 'tracked_cost_after_pair_usd': STATE['tracked_cost_usd'],
            'reserve_after_pair_usd': STATE['guard_reserve_usd']}
        (OUTPUT / 'first-pair-projection.json').write_text(json.dumps(projection, indent=2) + '\n')
        STATE['first_pair_projection'] = projection
        save()
        if projected > CAP: stop('projected_spend_stop')
    research = (document['result'].get('typed_outcome') or {}).get('research') or {}
    delivery_failed = bool(research and research.get('published') is False)
    STATE['candidate_research_delivery_failure_streak'] = STATE['candidate_research_delivery_failure_streak'] + 1 if delivery_failed else 0
    if STATE['candidate_research_delivery_failure_streak'] >= 3 and attempt < 10:
        cooldown = {'after_pair':attempt, 'before_pair':attempt+1, 'consecutive_candidate_delivery_failures':STATE['candidate_research_delivery_failure_streak'], 'started_at_epoch':time.time(), 'required_seconds':900}
        cooldown['resume_at_epoch'] = cooldown['started_at_epoch'] + 900
        STATE['cooldowns'].append(cooldown)
        STATE.update(state='provider_cooldown', cooldown_resume_at_epoch=cooldown['resume_at_epoch'])
        save()
        while time.time() < cooldown['resume_at_epoch']:
            if costs() >= CAP: stop('spend_stop')
            save()
            time.sleep(.5)
        cooldown['finished_at_epoch'] = time.time()
        STATE.pop('cooldown_resume_at_epoch',None)
        save()
STATE.update(state='completed', finished_at_epoch=time.time(), environment_source_unchanged_after_run=True)
save()
