"""Verify completed native measurements, budget, identity and private-data boundaries."""
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from dotenv import dotenv_values

control = Path(__file__).parent
root = Path('/Users/garces/.codex/worktrees/eca1/private-alpha-next')
evidence = root/'docs/reports/evidence/2026-09-12-main-promotion/sharing-off/eval'
source = control/'sharing-off-targeted-ab'
state = json.loads((source/'status.json').read_text())
assert state['state'] == 'completed'
assert [(x['attempt'], x['side']) for x in state['completed_attempts']] == [(n,s) for n in range(1,11) for s in ('baseline','candidate')]
expected_sha = state['shas']
rows = []
last_end = 0
native = {}
for item in state['completed_attempts']:
    raw = (source/item['artifact']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item['artifact_sha256']
    doc = json.loads(raw)
    assert doc['case_id'] == state['case_id']
    assert doc['provenance']['candidate_sha'] == expected_sha[item['side']]
    assert doc['provenance']['worktree_clean'] is True
    assert doc['started_at_epoch'] >= last_end
    last_end = doc['finished_at_epoch']
    result = doc['result']
    research = result['typed_outcome'].get('research')
    reason = (result['typed_outcome'].get('clarification') or {}).get('reason_code')
    timeout = bool(research and research.get('degraded_code') == 'research_unavailable_timeout')
    assert doc['measurement']['research_timeout'] == timeout
    assert doc['measurement']['failed'] == (result['status'] != 'passed' or timeout)
    http = [x['http_status'] for x in doc['research_http_errors']]
    assert all(isinstance(x,int) and x>=400 for x in http)
    if research:
        code = research.get('degraded_code')
        if research['published']:
            category = 'published_pass' if result['status']=='passed' else 'published_native_failure'
        elif code == 'research_unavailable_http_error':
            assert http, 'An HTTP research error is missing its captured status'
            category = 'provider_http_error'
        elif timeout:
            category = 'provider_timeout'
        elif isinstance(code,str) and code.startswith('research_unavailable_'):
            category = 'provider_other_unavailability'
        else:
            category = 'research_grounding_or_availability_guard'
    else:
        code = None
        category = 'future_performance_limitation' if reason=='future_performance' else 'no_research_other_path'
    rows.append({'attempt':item['attempt'],'side':item['side'],'native_status':result['status'],'failed':doc['measurement']['failed'],'category':category,'degraded_code':code,'http_error_statuses':http,'research_sources':research.get('sources') if research else None,'prose_judge_pass':(result.get('prose_judge') or {}).get('pass'),'failed_checks':result['failed_checks']})
    native[(item['attempt'], item['side'])] = doc
left, right = [native[(1,s)]['native_case'] for s in ('baseline','candidate')]
assert {k:v for k,v in left.items() if k not in {'expected','prose_judge'}} == {k:v for k,v in right.items() if k not in {'expected','prose_judge'}}
for c in state['cooldowns']:
    assert c['finished_at_epoch']-c['started_at_epoch'] >= 900
    assert native[(c['before_pair'],'baseline')]['started_at_epoch'] >= c['resume_at_epoch']
    assert c['consecutive_candidate_delivery_failures'] >= 3
source_env = Path(json.loads((control/'status.json').read_text())['environment']['ARGUS_EVAL_ENV_FILE'])
assert hashlib.sha256(source_env.read_bytes()).hexdigest() == state['environment_source_sha256']
events = [json.loads(x) for x in (control/'events.jsonl').read_text().splitlines()]
tracked = sum((Decimal(str(x['cost_usd'])) for x in events if x['kind']=='cost' and x['cost_usd'] is not None), Decimal(0))
unknown = sum(x.get('outcome')!='skipped' for x in events if x['kind']=='cost' and x['cost_usd'] is None)
reserve = Decimal('.10')+Decimal('.02')*unknown
assert float(tracked) == state['tracked_cost_usd']
assert float(reserve) == state['guard_reserve_usd']
assert tracked+reserve <= Decimal('12.50')
changed = subprocess.check_output(['git','diff','--name-only',expected_sha['candidate'],'HEAD'],cwd=root,text=True).splitlines()
assert all(x.startswith('docs/') for x in changed)
status = subprocess.check_output(['git','status','--porcelain','-z'],cwd=root).decode().split('\0')
assert all(not x or x[3:].startswith('docs/') for x in status)
subprocess.run(['git','merge-base','--is-ancestor','17a07497abbb2ff9159b9694832a6668421e0e88',expected_sha['candidate']],cwd=root,check=True)
def product_tree(sha):
    records = subprocess.check_output(['git','ls-tree','-rz','--full-tree',sha],cwd=root).split(b'\0')
    return b'\0'.join(x for x in records if x and not x.split(b'\t',1)[1].startswith(b'docs/'))
product = product_tree(expected_sha['candidate'])
assert product_tree('HEAD') == product
sensitive = [v.encode() for k,v in dotenv_values(source_env).items() if v and len(v)>=8 and re.search('KEY|TOKEN|PASSWORD|SECRET|DATABASE|POOLER',k)]
files = list(evidence.rglob('*')) + list((evidence.parent/'browser-completion').rglob('*'))
for path in files:
    if not path.is_file(): continue
    raw = path.read_bytes()
    assert not any(v in raw for v in sensitive), path.name
    assert not re.search(rb'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}',raw), path.name
summary = {side:dict(Counter(x['category'] for x in rows if x['side']==side)) for side in ('baseline','candidate')}
report = {'state':'pass','measured_product_sha':expected_sha['candidate'],'baseline_sha':expected_sha['baseline'],'promotion_head_before_evidence_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'non_docs_product_tree_sha256':hashlib.sha256(product).hexdigest(),'all_non_docs_paths_identical':True,'current_main_base_is_ancestor':True,'native_attempts_verified':20,'identical_user_inputs_both_sides':True,'all_attempts_sequential':True,'environment_source_unchanged':True,'tracked_cost_usd':float(tracked),'reserve_usd':float(reserve),'guarded_total_usd':float(tracked+reserve),'reserve_is_not_spend':True,'cap_usd':12.50,'cooldowns_verified':state['cooldowns'],'research_categories':summary,'attempt_outcomes':rows,'new_evidence_secret_scan_passed':True,'checked_at':datetime.now(timezone.utc).isoformat(),'scope':'Measurement and pre-commit product identity. Final CI and exact-head review must be verified on the eventual evidence commit before the PR terminal audit.'}
(evidence/'sharing-off-completion-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('state','native_attempts_verified','all_non_docs_paths_identical','guarded_total_usd','research_categories')}))
