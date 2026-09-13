"""Read-only reproduction on the disposable browser-walk records."""
import json,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
root=Path('/private/tmp/argus-promotion-20260912-acceptance')
sys.path.insert(0,str(root/'src'))
assert all(not p.exists() and not p.is_symlink() for p in (root/'.env',root/'web/.env.local'))
from argus.api.schemas import BacktestRun,EvidenceArtifact,Message
from argus.api.conversation_activity import _memory_result_hydrateable
from argus.domain.public_excerpt_turns import audit_text
from argus.domain.public_excerpts import PublicExcerptSourceError
query="begin read only; select jsonb_build_object('messages',(select jsonb_agg(to_jsonb(m)) from public.messages m),'jobs',(select jsonb_agg(to_jsonb(j)) from public.backtest_jobs j),'runs',(select jsonb_agg(to_jsonb(r)) from public.backtest_runs r),'artifacts',(select jsonb_agg(to_jsonb(a)) from public.evidence_artifacts a)); rollback;"
r=subprocess.run(['/usr/local/bin/docker','exec','supabase_db_argus-promotion-20260912','psql','-U','postgres','-d','postgres','-Atc',query],capture_output=True,text=True)
if r.returncode: print(r.stderr);raise SystemExit(r.returncode)
data=json.loads(next(x for x in r.stdout.splitlines() if x.startswith('{')))
runs=[BacktestRun.model_validate(x) for x in data['runs']]
artifacts=[EvidenceArtifact.model_validate(x) for x in data['artifacts']]
messages=[Message.model_validate(x) for x in data['messages']]
owner=data['runs'][0]['user_id']; conversation=runs[0].conversation_id
observed=SimpleNamespace(backtest_runs={x.id:x for x in runs},backtest_run_owners={x.id:owner for x in runs},evidence_artifacts={x.id:x for x in artifacts},evidence_artifact_owners={x.id:owner for x in artifacts},conversation_owners={conversation:owner},messages={conversation:messages})
job_proof=[{'scope':j['operation_scope'],'status':j['status'],'native_result_hydrateable':_memory_result_hydrateable(observed,user_id=owner,conversation_id=conversation,job=j)} for j in data['jobs']]
text_proof=[]
for n,m in enumerate(messages,1):
 if m.role!='assistant':continue
 try:audit_text(m.content,field='answer',private_ids=());outcome='pass'
 except PublicExcerptSourceError as exc:outcome=exc.reason
 meta=m.metadata or {};j_id=meta.get('backtest_job_id') or (meta.get('backtest_job') or {}).get('id')
 terminal=meta.get('agent_runtime_turn') or {}
 text_proof.append({'message_number':n,'answer_audit':outcome,'has_job_id':bool(j_id),'job_id_matches_saved_job':any(x['id']==j_id for x in data['jobs']),'terminal':terminal.get('terminal'),'terminal_status':terminal.get('status'),'has_research': 'research' in meta})
public_example='See [Coca-Cola second-quarter results](https://investors.coca-colacompany.com/news-events/press-releases/detail/1112/coca-cola-reports-second-quarter-2024-results-and-raises-full-year-guidance).'
try:audit_text(public_example,field='answer',private_ids=());example='pass'
except PublicExcerptSourceError as exc:example=exc.reason
report={'measured_sha':'df7aee12955f667e31057464d62c72287fb12247','read_only_local_database':True,'job_proof':job_proof,'answer_audits':text_proof,'public_publisher_link_audit':example,'public_example':public_example,'raw_private_identifiers_or_messages_retained':False}
Path('/Users/garces/.codex/worktrees/eca1/private-alpha-next/docs/reports/evidence/2026-09-12-main-promotion/browser-walk/sharing-diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
