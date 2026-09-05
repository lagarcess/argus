from pathlib import Path
import subprocess
import psycopg
url='postgresql://postgres:postgres@127.0.0.1:55482/postgres'
with psycopg.connect(url, autocommit=True) as db:
    for p in sorted(Path('temp/docn-conversion/integration/supabase/migrations').glob('*.sql')):
        if p.name == '20260724101324_add_guest_workspaces.sql':
            subprocess.run(['docker','exec','argus-docn-conversion-pg','psql','-U','supabase_admin','-d','postgres','-v','ON_ERROR_STOP=1','-c',"create or replace function auth.jwt() returns jsonb language sql stable as 'select coalesce(nullif(current_setting(''request.jwt.claims'', true), '''')::jsonb, ''{}''::jsonb)'; alter table auth.users add column if not exists is_anonymous boolean not null default false;"],check=True,capture_output=True)
        with db.transaction(): db.execute(p.read_text())
    print('Applied all integration migrations')
