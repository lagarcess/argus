import json
import subprocess
from pathlib import Path
root=Path('/Users/garces/.codex/worktrees/7e84/private-alpha-next')
case='messy_spanish_future_performance_nvda_cruce_dorado'
sides=[('baseline',Path('/private/tmp/argus-promotion-baseline-7e84'),'3d98057c1e722317f0243fb96fb647771ddae484'),('candidate',Path('/private/tmp/argus-promotion-ab-7e84'),'3cecda6933399e53f6ea00edc8004a88d7eefad4')]
logdir=root/'temp/release-evidence/targeted-logs';logdir.mkdir(exist_ok=True)
for n in range(1,11):
 for side,tree,sha in sides:
  log=logdir/f'{side}-{n:02}.log'
  with log.open('x') as output:
   process=subprocess.run([str(root/'.venv/bin/python'),'/private/tmp/argus-promotion-observer-7e84/targeted_driver.py','--tree',str(tree),'--expected-sha',sha,'--case-id',case,'--side',side,'--round',str(n)],stdout=output,stderr=subprocess.STDOUT)
  if process.returncode:raise SystemExit(f'{side} round {n} exited {process.returncode}; no retries')
  result=json.loads((tree/f'temp/release-evidence/targeted/{case}-{side}-{n:02}.json').read_text())
  print(json.dumps({'round':n,'side':side,'status':result['result']['status'],'elapsed_seconds':result['elapsed_seconds']}),flush=True)
