"""Adapted promotion watchdog; fail closed with an in-flight call reserve."""
import json,os,signal,time
from meter import meter,SCRATCH,EVIDENCE
pids=json.loads((SCRATCH/'server-pids.json').read_text())
while True:
    m=meter();phase=(SCRATCH/'phase.txt').read_text().strip();amount=m['replay_usd'] if phase=='replay' else m['smoke_usd'];limit=4 if phase=='replay' else 9
    (EVIDENCE/'meter.json').write_text(json.dumps(m,indent=2)+'\n')
    if amount+.65>=limit:
        (SCRATCH/'budget-stop.json').write_text(json.dumps({'phase':phase,'amount':amount,'limit':limit,'in_flight_reserve':.65}))
        os.killpg(pids['argus-api'],signal.SIGTERM);break
    try:os.kill(pids['argus-api'],0)
    except ProcessLookupError:break
    time.sleep(1)
