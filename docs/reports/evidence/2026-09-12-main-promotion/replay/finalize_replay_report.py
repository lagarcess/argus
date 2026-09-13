import json,hashlib,subprocess
from pathlib import Path
from datetime import datetime,timezone
root=Path(__file__).parent
repo=Path('/Users/garces/.codex/worktrees/eca1/private-alpha-next')
evidence=repo/'docs/reports/evidence/2026-09-12-main-promotion/replay'
state=json.loads((root/'replay-driver-status.json').read_text())
assert state['state'] in ['completed','blocked_by_failed_case']
verdicts=[json.loads(p.read_text()) for p in sorted(root.glob('case-*-turn-*.decision.json'))]
allowed={'case_number','turn_number','outcome','refusal_code','named_capability','allowance_code'}
assert all(set(v)<=allowed for v in verdicts)
assert len({(v['case_number'],v['turn_number']) for v in verdicts})==len(verdicts)
if state['state']=='completed':assert len(verdicts)==38 and state['distinct_fresh_guests']==15
budget=json.loads((root/'replay-budget-status.json').read_text())
assert budget['state']!='spend_stop'
tracked=budget['tracked_cost_usd'];reserve=budget['guard_reserve_usd']
assert tracked+reserve<4
cleanup=json.loads((root/'cleanup-replay.json').read_text())
assert cleanup['private_replay_directory_deleted'] and not cleanup['owned_containers_remaining'] and cleanup['supabase_stop_exit_code']==0
report={'status':state['state'],'candidate_sha':'df7aee12955f667e31057464d62c72287fb12247','environment':'C','cohort':'union of New York and UTC 2026-08-12 guest conversations; canary and internal excluded','planned_conversations':15,'planned_user_turns':38,'reported_price_before_execution_usd':.86,'completed_user_turns':len(verdicts),'passed_turns':sum(v['outcome']=='pass' for v in verdicts),'failed_turns':sum(v['outcome']=='fail' for v in verdicts),'allowance_turns':sum(v['outcome']=='allowance' for v in verdicts),'assessment':'Each user message and user-visible reply read privately against the board rule: no refusal naming a capability the user did not ask about. Usage and allowance messages counted separately.','native_driver_status':state,'tracked_cost_usd':tracked,'guard_reserve_usd':reserve,'guarded_total_usd':tracked+reserve,'cap_usd':4,'reserve_is_not_spend':True,'production_read_only':True,'fresh_guest_per_conversation':True,'ordered_user_messages':True,'browser_walk_pending_founder_approval':True,'private_inputs_frames_and_logs_deleted':True,'research_provider_errors':json.loads((root/'replay-provider-error-statuses.json').read_text())['research_provider_errors'],'checked_at':datetime.now(timezone.utc).isoformat(),'cases':verdicts}
evidence.mkdir(exist_ok=True)
(evidence/'replay-results.json').write_text(json.dumps(report,indent=2)+'\n')
for name in ['replay-run-decision.json','replay-budget-status.json','replay-costs.jsonl','environment-proof.json','restart-proof.json','replay-startup-health.json','replay-provider-error-statuses.json','replay-delivery-observations.json','cleanup-replay.json','replay_driver.py','pull_private_replay.py','launch_acceptance.py','watch_acceptance_budget.py','cleanup_replay.py','record_replay_verdict.py','finalize_replay_report.py']:
 path=root/name
 if path.exists():(evidence/name).write_bytes(path.read_bytes())
print(json.dumps({k:v for k,v in report.items() if k not in ['cases','native_driver_status','assessment']}))
