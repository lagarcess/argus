import hashlib
import json
import os
import signal
import subprocess
import time
from decimal import Decimal
from pathlib import Path

CONTROL = Path(__file__).parent
ROOT = Path('/Users/garces/.codex/worktrees/eca1/private-alpha-next')
VENV = ROOT / '.venv'
ENV = {
    'PATH': f'{VENV}/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin',
    'HOME': '/Users/garces',
    'VIRTUAL_ENV': str(VENV),
    'PYTHONPATH': f'src:web:{CONTROL}',
    'PYTEST_PLUGINS': 'promotion_observer',
    'PYTHONDONTWRITEBYTECODE': '1',
    'PYTHONUNBUFFERED': '1',
    'NUMBA_CACHE_DIR': str(CONTROL / 'numba-cache'),
    'ARGUS_RUN_LIVE_EVALS': '1',
    'ARGUS_EVAL_ENV_FILE': '/Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next/.env',
    'ARGUS_MARKET_DATA_PROVIDER_MODE': 'live_provider',
    'ARGUS_ASSET_PROVIDER_MODE': 'live_provider',
}
COMMAND = ['poetry', 'run', 'pytest', 'tests/evals/test_measurement_eval_live.py', '-q']
SHAS = {'baseline': 'ee9c3491fa6219502f1e94abc5d9e661a06839d9', 'candidate': 'df7aee12955f667e31057464d62c72287fb12247'}
status = {'state': 'preflight', 'command': COMMAND, 'shas': SHAS, 'combined_limit_usd': 3.5, 'environment': ENV, 'observer_sha256': hashlib.sha256((CONTROL/'promotion_observer.py').read_bytes()).hexdigest(), 'runs': {}, 'reported_cost_usd': 0}

def save():
    tmp = CONTROL / 'status.tmp'
    tmp.write_text(json.dumps(status, indent=2) + '\n')
    tmp.replace(CONTROL / 'status.json')

def spend():
    total = Decimal('0')
    unpriced = 0
    by_side = {}
    path = CONTROL / 'events.jsonl'
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event['kind'] != 'cost':
                continue
            cost = event['cost_usd']
            if cost is None:
                unpriced += event.get('outcome') != 'skipped'
            else:
                total += Decimal(str(cost))
                by_side[event['side']] = by_side.get(event['side'], Decimal('0')) + Decimal(str(cost))
    status.update(reported_cost_usd=float(total), cost_by_side={k: float(v) for k,v in by_side.items()}, unpriced_non_skipped_receipts=unpriced)
    # A conservative guard, not an invented price: reserve for one in-flight
    # request and missing receipt prices before reaching the founder's stop.
    reserve = Decimal('0.10') + Decimal('0.02') * unpriced
    status['unbilled_and_unpriced_guard_reserve_usd'] = float(reserve)
    return total + reserve >= Decimal('3.50')

for side, sha in SHAS.items():
    tree = Path(f'/private/tmp/argus-promotion-20260912-{side}-eval')
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=tree,text=True).strip() == sha
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=tree,text=True).strip()
    assert not (tree/'.env').exists() and not (tree/'web/.env.local').exists()
    code = "import argus, json, sys; from pathlib import Path; from tests.evals.measurement_eval_harness import load_eval_cases; root=Path.cwd(); assert Path(argus.__file__).resolve().is_relative_to(root); assert all(Path(m.__file__).resolve().is_relative_to(root) for n,m in sys.modules.items() if (n == 'argus' or n.startswith('argus.') or n.startswith('argus_display_contract')) and getattr(m,'__file__',None)); cases=load_eval_cases(); print(json.dumps({'argus_import_local':True,'all_imported_argus_modules_local':True,'cases':len(cases),'user_turns':sum(1+bool(c.followup_prompt) for c in cases)}))"
    result = subprocess.run(['poetry','run','python','-c',code],cwd=tree,env={k:v for k,v in ENV.items() if k != 'PYTEST_PLUGINS'},capture_output=True,text=True)
    if result.returncode:
        (CONTROL/f'{side}-preflight.log').write_text(result.stderr)
        status.update(state='preflight_failed', failed_side=side)
        save()
        raise SystemExit(1)
    status['runs'][side] = {'preflight': json.loads(result.stdout.strip().splitlines()[-1])}
save()
if '--preflight-only' in __import__('sys').argv:
    print(json.dumps({'state':status['state'],'runs':status['runs']}))
    raise SystemExit(0)
assert not (CONTROL/'events.jsonl').exists(), 'refuse to overwrite a live or completed pair'
for side, sha in SHAS.items():
    if spend():
        status['state'] = 'spend_stop'
        save()
        break
    tree = Path(f'/private/tmp/argus-promotion-20260912-{side}-eval')
    status.update(state='running', active_side=side)
    with (CONTROL/f'{side}.log').open('w') as log:
        child = subprocess.Popen(COMMAND,cwd=tree,env=ENV,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        status['runs'][side].update(pid=child.pid, started_at=time.time())
        save()
        while child.poll() is None:
            if spend():
                status['state'] = 'spend_stop'
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                break
            save()
            time.sleep(0.2)
        status['runs'][side].update(exit_code=child.wait(), finished_at=time.time())
    spend()
    save()
    if status['state'] == 'spend_stop':
        break
else:
    status['state'] = 'completed'
    status.pop('active_side', None)
    save()
