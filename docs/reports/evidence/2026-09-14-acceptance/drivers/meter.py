"""Content-free receipt meter. Unknown usage is an estimate, never zero."""
import json,sys
from pathlib import Path
from decimal import Decimal
EVIDENCE=Path(__file__).resolve().parent.parent
SCRATCH=Path('/private/tmp/argus-acceptance-20260914')
sys.path.insert(0,str((SCRATCH/'source' if SCRATCH.exists() else EVIDENCE.parents[3])/'src'))
from argus.domain.research.pricing import MODEL_RATE_TABLE_USD_PER_MILLION,TOOL_RATE_TABLE_USD_PER_INVOCATION

def estimate(event):
    u=event.get('usage') or {}
    if event['provider']=='openrouter':
        return .02,'unreported route receipt reserve; not provider-reported spend'
    rates=MODEL_RATE_TABLE_USD_PER_MILLION.get(event.get('model'))
    if rates and u.get('input_tokens') is not None and u.get('output_tokens') is not None:
        rate=rates[0] if u['input_tokens'] <= (rates[0].max_input_tokens or 10**9) else rates[-1]
        create=u.get('cache_creation_input_tokens') or 0;read=u.get('cache_read_input_tokens') or 0
        total=(Decimal(max(0,u['input_tokens']-create-read))*rate.input_usd_per_million+Decimal(create)*rate.cache_creation_input_usd_per_million+Decimal(read)*rate.cache_read_input_usd_per_million+Decimal(u['output_tokens'])*rate.output_usd_per_million)/Decimal(1000000)
        for tool,price in TOOL_RATE_TABLE_USD_PER_INVOCATION.items():total+=Decimal(u.get(tool+'_invocations') or 0)*price
        return float(total),'repository pricing table applied to recorded usage'
    # Missing invoice: conservative assumed 30k input + 15k output and 20
    # finance searches at the more expensive short-context table rate.
    rate=MODEL_RATE_TABLE_USD_PER_MILLION['anthropic/claude-opus-4-7'][0]
    value=(30000*rate.input_usd_per_million+15000*rate.output_usd_per_million)/Decimal(1000000)+20*TOOL_RATE_TABLE_USD_PER_INVOCATION['finance_search']
    return float(value),'missing usage: assumed 30k input, 15k output, 20 finance searches; table-priced reserve'

def meter():
    phases={}
    events=[]
    p=EVIDENCE/'cost-events.jsonl'
    for line in p.read_text().splitlines() if p.exists() else []:
        try:e=json.loads(line)
        except ValueError:continue
        events.append(e)
        if e.get('kind')!='cost' or e.get('outcome')=='skipped':continue
        phase=e['phase'];s=phases.setdefault(phase,{'reported_usd':0.,'unpriced_estimate_usd':0.,'receipts':0,'unpriced':[]})
        s['receipts']+=1
        if e.get('cost_usd') is not None:s['reported_usd']+=e['cost_usd']
        else:
            cost,basis=estimate(e);s['unpriced_estimate_usd']+=cost;s['unpriced'].append({'provider':e['provider'],'model':e.get('model'),'estimated_usd':cost,'basis':basis})
    # A transport timeout has no invoice callback. Reconcile unpriced durable
    # research turn rows as well, without double-counting observed unpriced invoices.
    # invoice_reconciliation is a diagnostic of the same invoice, not another call.
    import psycopg
    from psycopg.rows import dict_row
    cache=EVIDENCE/'unpriced-research-receipts.json'
    try:
        with psycopg.connect('postgresql://postgres:postgres@127.0.0.1:56732/postgres',connect_timeout=2,row_factory=dict_row) as connection:
            connection.execute('SET TRANSACTION READ ONLY')
            rows=connection.execute("select id, service, occurred_at from cost_ledger_entries where service != 'openrouter' and task != 'invoice_reconciliation' and cost_amount is null and cost_source='unavailable' order by occurred_at").fetchall()
        missing=[]
        for row in rows:
            prior=[e for e in events if e.get('time',0)<=row['occurred_at'].timestamp()]
            missing.append({'id':str(row['id']),'phase':prior[-1]['phase'] if prior else 'registered','provider':row['service']})
        cache.write_text(json.dumps(missing,indent=2)+'\n')
    except psycopg.OperationalError:
        if SCRATCH.exists():raise
        missing=json.loads(cache.read_text()) if cache.exists() else []
    for phase in {row['phase'] for row in missing}:
        observed=sum(e.get('phase')==phase and e.get('provider')!='openrouter' and e.get('cost_usd') is None and e.get('kind')=='cost' and e.get('outcome')=='served' for e in events)
        absent=[row for row in missing if row['phase']==phase][observed:]
        s=phases.setdefault(phase,{'reported_usd':0.,'unpriced_estimate_usd':0.,'receipts':0,'unpriced':[]})
        for row in absent:
            cost,basis=estimate(row)
            s['receipts']+=1;s['unpriced_estimate_usd']+=cost;s['unpriced'].append({**row,'estimated_usd':cost,'basis':basis})
    for s in phases.values():s['metered_usd']=s['reported_usd']+s['unpriced_estimate_usd']
    return {'phases':phases,'smoke_usd':sum(s['metered_usd'] for p,s in phases.items() if p!='replay'),'replay_usd':phases.get('replay',{}).get('metered_usd',0),'limits':{'smoke':9,'replay':4}}
if __name__=='__main__':
    result=meter();(EVIDENCE/'meter.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
