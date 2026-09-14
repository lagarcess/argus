"""Read back smoke-only durable receipts, costs and failure metadata."""
import json
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
ROOT=Path(__file__).resolve().parent.parent
with psycopg.connect('postgresql://postgres:postgres@127.0.0.1:56732/postgres',row_factory=dict_row) as conn:
    conn.execute('SET TRANSACTION READ ONLY')
    for path in sorted((ROOT/'turns').glob('*.json')):
        r=json.loads(path.read_text());cid=r['conversation_id'];mid=r['answer']['id']
        receipts=conn.execute('select * from public.route_receipts where conversation_id=%s order by created_at',(cid,)).fetchall()
        costs=conn.execute('select * from public.cost_ledger_entries where conversation_id=%s order by occurred_at',(cid,)).fetchall()
        stored=conn.execute('select metadata from public.messages where id=%s',(mid,)).fetchone()
        request=(stored['metadata'].get('agent_runtime_turn') or {}).get('request_id')
        def belongs(row):return str(row.get('message_id'))==mid or request and (row.get('request_id')==request or (row.get('metadata') or {}).get('request_id')==request)
        r['stored_route_receipts']=[row for row in receipts if belongs(row)]
        r['stored_cost_ledger']=[row for row in costs if belongs(row)]
        r['conversation_route_receipt_count']=len(receipts)
        r['stored_failure_metadata']={k:v for k,v in stored['metadata'].items() if k in ('agent_runtime_turn','agent_runtime_stage_outcome','clarification','research','tool_result_cards','unsupported','failure')}
        path.write_text(json.dumps(r,indent=2,ensure_ascii=False,default=str)+'\n')
print('Stored smoke evidence attached')
