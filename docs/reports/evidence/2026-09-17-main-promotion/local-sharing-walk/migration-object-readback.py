import os,json,subprocess,hashlib
from pathlib import Path
import psycopg
root=Path('/Users/garces/.codex/worktrees/7e84/private-alpha-next')
base=Path('/private/tmp/argus-share-walk-db-7e84')
out=root/'docs/reports/evidence/2026-09-17-main-promotion/local-sharing-walk'
s=json.loads((base/'status.json').read_text())
e=os.environ.copy();e['ARGUS_DISPOSABLE_DATABASE_URL']=s['DB_URL'];e['PYTHONPATH']=str(root)
subprocess.run([str(root/'.venv/bin/python'),str(root/'docs/reports/evidence/promotion-readiness/rehearse_migrations.py'),'--candidate-sha','cfc1988dd80ca1a8007b8f336c107700dd57e009','--output',str(out/'migrations-after.json')],env=e,check=True)
with psycopg.connect(s['DB_URL'],sslmode='disable',row_factory=psycopg.rows.dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY')
 constraints=c.execute("SELECT conname AS name, pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conname IN ('public_excerpt_snapshots_kind_check','route_receipts_tier_check') ORDER BY conname").fetchall()
 funcs=c.execute("SELECT oid::regprocedure::text AS signature,prosecdef AS security_definer,pg_get_functiondef(oid) AS definition,has_function_privilege('anon',oid,'EXECUTE') AS anon_execute,has_function_privilege('authenticated',oid,'EXECUTE') AS authenticated_execute,has_function_privilege('service_role',oid,'EXECUTE') AS service_role_execute FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname IN ('claim_research_usage','release_research_usage') ORDER BY proname").fetchall()
 for f in funcs:f['definition_sha256']=hashlib.sha256(f.pop('definition').encode()).hexdigest()
r={'target':'disposable-local-argus-share-walk-7e84','production_access':False,'constraints':constraints,'functions':funcs}
(out/'objects-after.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
