import json,os,sys
from pathlib import Path
root=Path(__file__).parent
state=json.loads((root/'replay-driver-status.json').read_text())
assert state['state']=='awaiting_semantic_assessment'
assert int(sys.argv[1])==state['case_number'] and int(sys.argv[2])==state['turn_number']
outcome=sys.argv[3]
assert outcome in ['pass','fail','allowance']
assert state['http_status']==200 or outcome=='allowance'
if outcome=='pass':assert state['done_count']==1
verdict={'case_number':state['case_number'],'turn_number':state['turn_number'],'outcome':outcome,'refusal_code':None,'named_capability':None}
if outcome=='fail':
 assert len(sys.argv)==6
 verdict['refusal_code']=sys.argv[4]
 verdict['named_capability']=sys.argv[5]
if outcome=='allowance':
 assert len(sys.argv)==5
 verdict['allowance_code']=sys.argv[4]
path=root/f'case-{state["case_number"]:02d}-turn-{state["turn_number"]:02d}.decision.json'
with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as f:f.write(json.dumps(verdict,indent=2)+'\n')
print(json.dumps(verdict))
