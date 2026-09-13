"""Read the approved cohort once, keeping only private numbered inputs."""
import json
import os
import re
from pathlib import Path

import psycopg
from dotenv import dotenv_values

root = Path(__file__).parent
decision = json.loads((root / 'replay-run-decision.json').read_text())
assert decision['ab_completed'] and decision['founder_replay_authorized_after_ab']
assert decision['reported_before_execution'] and decision['estimated_cost_usd'] <= 4
assert decision['window'] == 'union_august_12'
inventory = json.loads((root / 'replay-union-counts.json').read_text())
window = inventory['windows'][decision['window']]
expected = next(group for group in window['groups'] if group['guest'] and not group['excluded'])
private = root / 'private-replay'
private.mkdir(mode=0o700, exist_ok=False)
source = dotenv_values('/Users/garces/Documents/projects/repos/argus-worktrees/private-alpha-next/.env')
dsn = source['SUPABASE_POSTGRES_SESSION_POOLER_URL']
assert 'lgdhvepyrzbnscqssgqq' in dsn
try:
    with psycopg.connect(dsn, sslmode='verify-full', sslrootcert='/Users/garces/.argus/prod-ca-2021.crt',
                          gssencmode='disable', connect_timeout=15, autocommit=True) as connection:
        connection.execute('BEGIN TRANSACTION READ ONLY')
        assert connection.execute('SHOW transaction_read_only').fetchone()[0] == 'on'
        connection.execute("SET LOCAL statement_timeout='20000'")
        rows = connection.execute('''
            with cohort as (
                select c.id, c.language, min(m.created_at) as first_turn
                from public.conversations c
                join public.messages m on m.conversation_id=c.id and m.role='user'
                left join public.profiles p on p.id=c.user_id
                left join auth.users u on u.id=c.user_id
                left join public.guest_workspaces g on g.user_id=c.user_id
                where (coalesce(u.is_anonymous,false) or g.user_id is not null)
                  and not (coalesce(p.is_admin,false)
                    or lower(coalesce(u.raw_app_meta_data->>'source','')) like '%%canary%%'
                    or lower(coalesce(p.email,u.email,'')) ~ '(canary|internal|developer@|^test[+._-]|^qa[+._-])')
                  and exists (select 1 from public.messages selected
                    where selected.conversation_id=c.id and selected.role='user'
                      and selected.created_at >= %s::timestamptz
                      and selected.created_at < %s::timestamptz)
                group by c.id,c.language
            )
            select c.id,c.language,m.content
            from cohort c join public.messages m on m.conversation_id=c.id and m.role='user'
            order by c.first_turn,c.id,m.created_at,m.id
        ''', (window['start'], window['end'])).fetchall()
        connection.execute('ROLLBACK')
except Exception as exc:
    error = f'{type(exc).__name__}: {exc}'
    for key, value in source.items():
        if value and len(value) >= 8 and re.search('KEY|TOKEN|PASSWORD|SECRET|DATABASE|POOLER', key):
            error = error.replace(value, '<redacted>')
    print(error)
    raise SystemExit(1)
cases = []
last_identity = None
for identity, language, content in rows:
    if identity != last_identity:
        cases.append({'case_number': len(cases) + 1, 'language': language or 'en', 'messages': []})
        last_identity = identity
    assert isinstance(content, str) and content.strip(), 'Replay input is not a nonempty user message'
    cases[-1]['messages'].append(content)
assert len(cases) == expected['conversations'], 'Replay cohort count changed'
assert sum(len(case['messages']) for case in cases) == expected['user_turns'], 'Replay turn count changed'
path = private / 'inputs.json'
with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as output:
    json.dump({'cases': cases}, output, ensure_ascii=False)
print(json.dumps({'private_input_saved': True, 'production_read_only': True,
                  'conversations': len(cases), 'user_turns': expected['user_turns'],
                  'identities_serialized': False, 'content_printed': False}))
