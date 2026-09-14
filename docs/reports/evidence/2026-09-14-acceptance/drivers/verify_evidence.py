"""Validate evidence completeness and the private replay export contract offline."""
import hashlib,json,struct
from pathlib import Path
P=Path(__file__).resolve().parent.parent
v=json.loads((P/'verdicts.json').read_text())
records={p.stem:json.loads(p.read_text()) for p in (P/'turns').glob('*.json')}
expected={f'{phase}-q{n}-{lang}' for phase in ['registered','followups','guest'] for lang in ['en','es-419'] for n in ([1,7,9] if phase=='guest' else range(1,11))}
assert records.keys()==expected and v.keys()==expected
for label,r in records.items():
 assert isinstance(v[label]['pass'],bool) and v[label]['reason']
 assert r.get('stored_route_receipts') and 'stored_failure_metadata' in r
 image=P/r['screenshot']['file'];raw=image.read_bytes();assert raw[:8]==b'\x89PNG\r\n\x1a\n'
 assert struct.unpack('>II',raw[16:24])==(390,844)
 if r['phase']!='guest':assert r['country']==('US' if r['language']=='en' else 'DO')
 if r['phase']=='followups':assert r['conversation_id']==records[label.replace('followups-','registered-')]['conversation_id']
comparisons=json.loads((P/'baseline-comparison.json').read_text());assert len(comparisons)==20
repo=P.parents[3]
for c in comparisons:assert hashlib.sha256((repo/c['baseline_answer']).read_bytes()).hexdigest()==c['baseline_sha256'] and c['comparison']
replay=json.loads((P/'replay-results.json').read_text())
for r in replay['turns']:
 assert not set(r)&{'user_message','content','stored_messages','frames','conversation_id','user_id'}
 assert r['outcome'] in ['pass','fail','allowance'] and r['reason']
 for row in r['stored_routes']+r['stored_costs']:assert not set(row)&{'metadata','content','user_id','conversation_id','message_id','request_id'}
assert replay['passed']+replay['failed']+replay['allowance']+replay['not_run']==38
proof={'smoke_records':len(records),'phone_images':len(records),'phone_dimensions':[390,844],'all_followups_use_original_conversation':True,'all_registered_countries_match':True,'all_turns_have_routes_and_failure_metadata':True,'baseline_comparisons':20,'smoke_passed':sum(x['pass'] for x in v.values()),'smoke_failed':sum(not x['pass'] for x in v.values()),'replay_assessed':len(replay['turns']),'replay_export_key_check':'pass'}
(P/'verification.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
