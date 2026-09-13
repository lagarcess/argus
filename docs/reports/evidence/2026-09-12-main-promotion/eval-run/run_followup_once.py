"""Run one authorized judge replay or case retry under the cumulative guard."""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

control = Path(__file__).parent
phase = sys.argv[1]
assert phase in ('recorded_judge', 'case_retry')
original = json.loads((control / 'status.json').read_text())
full = json.loads((control / 'candidate-approved-retry-status.json').read_text())
assert full['state'] == 'completed'
env = original['environment']
tree = Path('/private/tmp/argus-promotion-20260912-candidate-eval')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=tree,text=True).strip() == full['candidate_sha']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=tree,text=True).strip()
assert hashlib.sha256(Path(env['ARGUS_EVAL_ENV_FILE']).read_bytes()).hexdigest() == full['environment_source_sha256']
if phase == 'case_retry':
    assert (control / 'recorded-judge-replay.json').exists()
assert not any(json.loads(path.read_text()).get('state') == 'spend_stop' for path in control.glob('followup-*-status.json'))
status = {'phase':phase,'state':'preflight','combined_limit_usd':full['combined_limit_usd'],
          'candidate_sha':full['candidate_sha'],'environment_identical_to_full_run':True,
          'initial_event_count':len((control / 'events.jsonl').read_text().splitlines())}
path = control / f'followup-{phase}-status.json'

def update():
    total = Decimal('0')
    unknown = 0
    for line in (control / 'events.jsonl').read_text().splitlines():
        try:event = json.loads(line)
        except ValueError:continue
        if event['kind'] != 'cost':continue
        if event['cost_usd'] is None:unknown += event.get('outcome') != 'skipped'
        else:total += Decimal(str(event['cost_usd']))
    reserve = Decimal('0.10') + Decimal('0.02') * unknown
    status.update(tracked_cost_usd=float(total),guard_reserve_usd=float(reserve),
                  guarded_total_usd=float(total+reserve),unpriced_non_skipped_receipts=unknown)
    return total+reserve >= Decimal(str(full['combined_limit_usd']))

def save():
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(status,indent=2)+'\n')
    tmp.replace(path)

assert not update(), 'Already at combined guard cap'
with os.fdopen(os.open(control / f'followup-{phase}-once.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as lock:
    lock.write(str(time.time())+'\n')
command = ['poetry','run','pytest','-c',str(tree/'pyproject.toml'),str(control/'test_approved_followup.py'),'-q','-k',phase]
with (control/f'followup-{phase}.log').open('w') as log:
    child = subprocess.Popen(command,cwd=tree,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    status.update(state='running',pid=child.pid,command=command,started_at=time.time())
    save()
    while child.poll() is None:
        if update():
            status['state']='spend_stop'
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL)
            break
        save()
        time.sleep(0.2)
    status.update(exit_code=child.wait(),finished_at=time.time())
update()
if status['state']=='running':status['state']='completed'
status['environment_source_unchanged_after_run']=hashlib.sha256(Path(env['ARGUS_EVAL_ENV_FILE']).read_bytes()).hexdigest()==full['environment_source_sha256']
save()
