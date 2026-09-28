import hashlib,json
from decimal import Decimal
from pathlib import Path
case='messy_spanish_future_performance_nvda_cruce_dorado'
out=Path('docs/reports/evidence/2026-09-17-main-promotion')
review=json.loads(Path('temp/release-evidence/targeted-review.json').read_text())
progress=[json.loads(x) for x in Path('temp/release-evidence/targeted-progress.jsonl').read_text().splitlines()]
assert [(x['round'],x['side']) for x in progress]==[(n,s) for n in range(1,11) for s in ('baseline','candidate')]
for side,tree in [('baseline',Path('/private/tmp/argus-promotion-baseline-7e84')),('candidate',Path('/private/tmp/argus-promotion-ab-7e84'))]:
 records=[]
 for n in range(1,11):
  d=json.loads((tree/f'temp/release-evidence/targeted/{case}-{side}-{n:02}.json').read_text());d['specific_defect_review']=review[f'{side}-{n:02}'];records.append(d)
 provenance=records[0]['provenance']
 assert all(r['provenance']['candidate_sha']==provenance['candidate_sha'] and r['provenance']['release_configuration']==provenance['release_configuration'] and r['provenance']['worktree_clean'] and r['configuration_before_after_match'] for r in records)
 results=[r['result'] for r in records];receipts=[x for r in results for x in r['route_receipts']]
 pub=sum((r.get('typed_outcome',{}).get('research') or {}).get('published') is True for r in results)
 defect=sum(r['specific_defect_review']['empty_scenario_table'] for r in records)
 payload={'case_id':case,'side':side,'provenance':provenance,'method':'Ten serial interleaved rounds; baseline then candidate per round; native product path and original case, no manual retries or judge-only replay. Human inspection of retained response text counts the specific defect independently of judge labels.','specific_defect':'Response promises or presents a scenario table but includes only the header/separator and no scenario rows.','measurement':{'attempts':len(records),'empty_scenario_table_count':defect,'empty_scenario_table_rate':defect/len(records),'published_research_count':pub,'not_published_research_count':sum((r.get('typed_outcome',{}).get('research') or {}).get('published') is False for r in results),'routing_without_research_count':sum(r.get('typed_outcome',{}).get('research') is None for r in results),'failed_case_count':sum(r['status']=='failed' for r in results),'judge_failure_count':sum((r.get('prose_judge') or {}).get('pass') is False for r in results),'empty_table_rate_among_published_answers':defect/pub if pub else None},'usage':{'route_receipt_count':len(receipts),'reported_cost_usd':str(sum((Decimal(str(x['usage_cost_usd'])) for x in receipts if x.get('usage_cost_usd') is not None),Decimal(0))),'unreported_cost_receipt_count':sum(x.get('usage_cost_usd') is None for x in receipts)},'elapsed_seconds':sum(r['elapsed_seconds'] for r in records),'attempt_records':records}
 (out/f'spanish-scenario-ab-{side}.json').write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({k:v for k,v in payload.items() if k not in ('attempt_records','provenance')},indent=2))
(out/'targeted-execution-order.json').write_text(json.dumps(progress,indent=2)+'\n')
