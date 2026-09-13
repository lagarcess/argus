"""Preserve every native attempt after the approved ten-pair continuation."""
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime, timezone
from dotenv import dotenv_values

control = Path(__file__).parent
source = control/'targeted-ab'
root = Path('/Users/garces/.codex/worktrees/eca1/private-alpha-next')
evidence = root/'docs/reports/evidence/2026-09-12-main-promotion'
target = evidence/'targeted-ab'
state = json.loads((source/'resume-status.json').read_text())
assert state['state'] == 'completed', 'Do not finalize an incomplete measurement'
assert [(a['attempt'],a['side']) for a in state['completed_attempts']] == [(n,s) for n in range(1,11) for s in ('baseline','candidate')]
secret_values = [v.encode() for k,v in dotenv_values('/Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next/.env').items() if v and len(v)>=8 and re.search('KEY|TOKEN|PASSWORD|SECRET|DATABASE|POOLER',k)]
def checked_write(path,raw):
    assert not any(v in raw for v in secret_values), path.name
    assert not re.search(rb'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',raw), path.name
    path.write_bytes(raw)
for path in [*source.glob('*.json'),*source.glob('*.log'), control/'resume_interleaved_ab.py', control/'test_interleaved_ab.py',control/'promotion_http_observer.py',control/'http-observer-free-check.json',Path(__file__)]:
    raw=path.read_bytes()
    if path.suffix=='.log': raw=('\n'.join(x.rstrip() for x in raw.decode().splitlines())+'\n').encode()
    checked_write(target/path.name,raw)
all_events=(control/'events.jsonl').read_text().splitlines()
checked_write(target/'events.jsonl', ('\n'.join(all_events[state['initial_event_count']:])+'\n').encode())
checked_write(evidence/'eval-run/all-attempt-events.jsonl', ('\n'.join(all_events)+'\n').encode())
summary={}
for side in ('baseline','candidate'):
    attempts=[]
    for record in state['completed_attempts']:
        if record['side']!=side:continue
        raw=(source/record['artifact']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==record['artifact_sha256']
        attempts.append(json.loads(raw))
    assert len(attempts)==10
    provenance=attempts[0]['provenance']
    assert all(a['provenance']==provenance for a in attempts)
    assert provenance['candidate_sha']==state['shas'][side] and provenance['worktree_clean']
    assert all(a['targeted_case_sha256']==attempts[0]['targeted_case_sha256'] for a in attempts)
    failed=sum(a['measurement']['failed'] for a in attempts)
    timeouts=sum(a['measurement']['research_timeout'] for a in attempts)
    assert failed==state['failures'][side] and timeouts==state['research_timeouts'][side]
    measurement={'attempts':10,'failed_count':failed,'failed_rate':failed/10,'passed_count':10-failed,'passed_rate':(10-failed)/10,'research_timeout_count':timeouts,'research_timeout_rate':timeouts/10,'criterion':'Any native non-pass or research timeout is a failed attempt. No attempt is discarded.','fixture_comparison_note':'Inputs are identical. Each build retains its committed typed expectations and prose rubric; production expects a future-performance limitation, candidate expects researched scenarios.'}
    doc={'schema_version':1,'scorecard_kind':'live_targeted_interleaved_ab','case_id':state['case_id'],'side':side,'provenance':provenance,'targeted_case_sha256':attempts[0]['targeted_case_sha256'],'native_case':attempts[0]['native_case'],'environment_identical_to_completed_pair':True,'environment_source_sha256':state['environment_source_sha256'],'generated_at':datetime.now(timezone.utc).isoformat(),'paired_execution':{'order':state['order'],'planned_rounds':10,'completed_attempt_numbers':list(range(1,11)),'state':state['state']},'measurement':measurement,'founder_disposition_document':'founder-research-disposition.json','attempts':attempts}
    checked_write(evidence/f'targeted-ab-{side}.json',(json.dumps(doc,indent=2,ensure_ascii=False)+'\n').encode())
    summary[side]=measurement
comparison=json.loads((evidence/'approved-eval-comparison.json').read_text())
comparison.update(status='ab_completed_founder_merge_disposition_pending',**{k:state[k] for k in ('tracked_cost_usd','guard_reserve_usd','guarded_total_usd','combined_cap_usd')})
comparison['targeted_ab']={'state':state['state'],'measurements':summary,'candidate_failure_excess':state['failures']['candidate']-state['failures']['baseline'],'failure_gap_stop_applies':False,'baseline_document':'targeted-ab-baseline.json','candidate_document':'targeted-ab-candidate.json','founder_disposition_document':'founder-research-disposition.json'}
checked_write(evidence/'approved-eval-comparison.json',(json.dumps(comparison,indent=2)+'\n').encode())
print(json.dumps({'state':state['state'],'measurements':summary,'guarded_total_usd':state['guarded_total_usd']}))
