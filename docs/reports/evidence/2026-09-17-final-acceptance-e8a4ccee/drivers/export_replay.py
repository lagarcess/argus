"""Export only allowlisted operational metadata and human verdicts, never text."""
import json,os,sys
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
P=Path(__file__).resolve().parent.parent
ROOT=Path(__file__).resolve().parents[5]
if str(ROOT) not in sys.path:
 sys.path.insert(0,str(ROOT))
from tests.evals.acceptance_attribution import (  # noqa: E402
 allowlisted_cost_row,
 allowlisted_failure_metadata,
 allowlisted_route_row,
)
REPEAT=os.environ.get('ACCEPTANCE_PRIVATE_REPEAT')=='1'
R=Path('/private/tmp/argus-acceptance-20260917-e8a4ccee')/('replay-repeat-control' if REPEAT else 'replay-control')
records=[]
with psycopg.connect('postgresql://postgres:postgres@127.0.0.1:56732/postgres',row_factory=dict_row) as conn:
 conn.execute('SET TRANSACTION READ ONLY')
 for path in sorted((R/'private-replay').glob('case-*.private.json')):
  d=json.loads(path.read_text());decision=R/path.name.replace('.private.json','.decision.json')
  if not decision.exists():continue
  v=json.loads(decision.read_text());assessment=R/path.name.replace('.private.json','.assessment.json')
  if assessment.exists():v.update(json.loads(assessment.read_text()))
  items=d['stored_messages'].get('items',[])
  assistant=[x for x in items if x.get('role')=='assistant'][-1:]
  r={**v,'http_status':d['http_status'],'done_count':d['done_count'],'stored_routes':[],'stored_costs':[],'stored_failure_metadata':{}}
  if assistant:
   a=assistant[0];meta=a.get('metadata') or {};mid=a['id'];request=(meta.get('agent_runtime_turn') or {}).get('request_id')
   rows=conn.execute('select * from route_receipts where message_id=%s or metadata->>\'request_id\'=%s order by created_at',(mid,request)).fetchall()
   costs=conn.execute('select * from cost_ledger_entries where message_id=%s or request_id=%s order by occurred_at',(mid,request)).fetchall()
   r['stored_routes']=[allowlisted_route_row(x) for x in rows]
   r['stored_costs']=[allowlisted_cost_row(x) for x in costs]
   r['stored_failure_metadata']=allowlisted_failure_metadata(meta, routes=rows)
  records.append(r)
inputs=json.loads((R/'private-replay/inputs.json').read_text())
report={'product_sha':'e8a4ccee45c390180d2979881a977fcd050f6b1b','cohort':{'window':'union of UTC and America/New_York 2026-08-12','conversations':len(inputs['cases']),'user_turns':sum(len(c['messages']) for c in inputs['cases']),'internal_and_canary_excluded':True,'fresh_guest_per_started_conversation':True},'turns':records,'passed':sum(r['outcome']=='pass' for r in records),'failed':sum(r['outcome']=='fail' for r in records),'allowance':sum(r['outcome']=='allowance' for r in records),'not_run':sum(len(c['messages']) for c in inputs['cases'])-len(records),'customer_text_included':False}
report['not_run_turns']=[{'case_number':c['case_number'],'turn_number':n,'reason':('attempted_unassessed' if (R/'private-replay'/f'case-{c["case_number"]:02d}-turn-{n:02d}.private.json').exists() else 'not_started')} for c in inputs['cases'] for n in range(1,len(c['messages'])+1) if (c['case_number'],n) not in {(r['case_number'],r['turn_number']) for r in records}]
(P/('replay-repeat-results.json' if REPEAT else 'replay-results.json')).write_text(json.dumps(report,indent=2,default=str)+'\n')
print({k:v for k,v in report.items() if k not in ['turns','not_run_turns']})
