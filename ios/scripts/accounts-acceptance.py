"""Real local HTTP checks; credentials and raw responses stay in ignored lane state."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'ios/.build/accounts-local'
EVIDENCE = ROOT / 'docs/reports/evidence/ios-financial-accounts'
CONFIG = json.loads((WORK / 'client.json').read_text())
if CONFIG['apiURL'] != 'http://127.0.0.1:58400/api/v1' or CONFIG['supabaseURL'] != 'http://127.0.0.1:58401':
    raise SystemExit('Refusing non-lane endpoints')
STATE = WORK / 'api-private.json'
checks = []


def private_write(value):
    fd = os.open(STATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as handle:
        json.dump(value, handle)


def raw(url, method='GET', body=None, headers=None):
    req = urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(), method=method,
                                 headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def check(name, condition):
    if not condition:
        raise SystemExit('Acceptance failed: ' + name)
    checks.append(name)


def request(state, user, method, suffix='', body=None, key=None):
    session = state['sessions'][user]
    headers = {'Authorization': 'Bearer ' + session['access_token']}
    if key is not None:
        headers['Idempotency-Key'] = key
    result = raw(CONFIG['apiURL'] + '/financial-accounts' + suffix, method, body, headers)
    if result[0] == 401:
        code, renewed = raw(CONFIG['supabaseURL'] + '/auth/v1/token?grant_type=refresh_token', 'POST',
                            {'refresh_token': session['refresh_token']}, {'apikey': CONFIG['publicAnonKey']})
        check('refresh session', code == 200)
        state['sessions'][user] = renewed
        private_write(state)
        headers['Authorization'] = 'Bearer ' + renewed['access_token']
        result = raw(CONFIG['apiURL'] + '/financial-accounts' + suffix, method, body, headers)
    return result


def journey():
    if STATE.exists():
        raise SystemExit('Journey already has private state; use readback, never remint silently')
    state = {'sessions': [], 'records': {}}
    for user in CONFIG['users']:
        code, session = raw(CONFIG['apiURL'] + '/auth/login', 'POST',
                            {'email': user['email'], 'password': user['password'], 'captcha_token': 'XXXX.DUMMY.TOKEN.XXXX'})
        check('registered local login', code == 200 and 'access_token' in session.get('session', {}))
        state['sessions'].append(session['session'])
    private_write(state)
    def call(method, suffix='', body=None, expected=200, error=None, key=None, user=0):
        status, result = request(state, user, method, suffix, body, key)
        check(f'{method} {error or expected}', status == expected and (error is None or result.get('code') == error))
        return result
    def create(label, **fields):
        payload = {'type': 'checking', 'currency': 'USD', 'nickname': label,
                   'as_of': '2026-09-01T09:00:00-04:00', 'time_zone': 'America/Santo_Domingo', **fields}
        key = str(uuid.uuid4())
        record = call('POST', body=payload, key=key, expected=201)
        # Deliberately discard original response at the client boundary, replay exact body/key.
        replay = call('POST', body=payload, key=key)
        check('immutable replay returns original id/version', replay == record)
        state['records'][label] = record
        private_write(state)
        return record, payload, key
    known, payload, key = create('Known local account', amount='1234.56')
    call('POST', body={**payload, 'amount': '1234.57'}, key=key, expected=409, error='idempotency_conflict')
    zero, _, _ = create('Zero local account', amount='0')
    unknown, _, _ = create('Unknown local account')
    large, _, _ = create('Exact large local account', amount='90071992547409.93')
    check('known zero is distinct from unknown', zero['balance']['amount'] == '0.00' and unknown['balance']['state'] == 'unknown')
    check('large decimal and minor units remain exact', large['balance']['amount'] == '90071992547409.93' and large['balance']['amount_minor'] == 9007199254740993)
    debt, _, _ = create('Debt local account', type='credit_card', amount='100')
    check('positive owed input becomes owner-signed negative', debt['balance']['amount'] == '-100.00')
    debt = call('PUT', '/' + debt['id'] + '/opening', {'expected_version': debt['version'], 'expected_revision': 1, 'amount': '125', 'reason': 'Correct local amount'})
    check('debt correction signs once', debt['balance']['amount'] == '-125.00')
    debt = call('PUT', '/' + debt['id'] + '/opening', {'expected_version': debt['version'], 'expected_revision': 2, 'as_of': '2026-09-02T09:00:00-04:00', 'reason': 'Correct local date'})
    check('date-only debt correction preserves signed amount and stored zone', debt['balance']['amount'] == '-125.00' and debt['opening']['time_zone'] == 'America/Santo_Domingo' and len(debt['opening']['revisions']) == 3)
    state['records']['Debt local account'] = debt
    modified = call('PATCH', '/' + known['id'], {'expected_version': known['version'], 'nickname': ''})
    check('explicit blank nickname clears', modified['nickname'] is None)
    call('PATCH', '/' + known['id'], {'expected_version': known['version'], 'nickname': 'stale'}, expected=409, error='stale_version')
    call('PATCH', '/' + known['id'], {'expected_version': modified['version'], 'currency': 'JPY'}, expected=422, error='currency_locked')
    archived = call('PATCH', '/' + known['id'], {'expected_version': modified['version'], 'archived': True})
    check('archive retains balance', archived['archived'] and archived['balance'] == known['balance'])
    restored = call('PATCH', '/' + known['id'], {'expected_version': archived['version'], 'archived': False})
    check('restore retains balance', not restored['archived'] and restored['balance'] == known['balance'])
    state['records']['Known local account'] = restored
    for field, value in [('currency', 'JPY'), ('type', 'credit_card')]:
        empty, _, _ = create('Stale ' + field)
        edited = call('PATCH', '/' + empty['id'], {'expected_version': empty['version'], field: value})
        call('PUT', '/' + empty['id'] + '/opening', {'expected_version': empty['version'], 'expected_revision': None, 'amount': '100'}, expected=409, error='stale_version')
        check('stale metadata never creates opening', call('GET', '/' + empty['id'])['opening'] is None)
        state['records']['Stale ' + field] = edited
    call('PUT', '/' + unknown['id'] + '/opening', {'expected_revision': None, 'amount': '1'}, expected=422)
    opening = call('PUT', '/' + unknown['id'] + '/opening', {'expected_version': unknown['version'], 'expected_revision': None, 'amount': '50', 'time_zone': 'America/Santo_Domingo'})
    check('first opening moves unknown to known', opening['balance']['amount'] == '50.00')
    state['records']['Unknown local account'] = opening
    call('GET', '/' + known['id'], expected=404, error='financial_account_not_found', user=1)
    call('PATCH', '/' + known['id'], {'expected_version': restored['version'], 'nickname': 'forbidden'}, expected=404, error='financial_account_not_found', user=1)
    check('owner B list excludes A records', known['id'] not in [x['id'] for x in call('GET', user=1)['accounts']])
    for patch, error in [({'amount': '1.001'}, 'amount_precision'), ({'amount': '92233720368547758.08'}, 'amount_out_of_range'), ({'amount': '1,00'}, 'amount_invalid'), ({'currency': 'ZZZ'}, 'currency_unsupported'), ({'as_of': '2026-09-01T09:00:00'}, 'date_invalid'), ({'as_of': '2099-01-01T00:00:00Z'}, 'date_in_future'), ({'time_zone': 'Invalid/Zone'}, 'time_zone_invalid')]:
        call('POST', body={**payload, **patch}, key=str(uuid.uuid4()), expected=422, error=error)
    call('PUT', '/' + debt['id'] + '/opening', {'expected_version': debt['version'], 'expected_revision': 3, 'amount': '1'}, expected=422, error='reason_required')
    check('unauthenticated request refused', raw(CONFIG['apiURL'] + '/financial-accounts')[0] == 401)
    private_write(state)


def readback():
    state = json.loads(STATE.read_text())
    for record in state['records'].values():
        code, actual = request(state, 0, 'GET', '/' + record['id'])
        check('API restart preserves exact accepted record', code == 200 and actual == record)


def unavailable():
    code, value = raw(CONFIG['apiURL'] + '/financial-accounts')
    check('flag off unavailable before authentication', code == 404 and value.get('code') == 'financial_accounts_unavailable')


parser = argparse.ArgumentParser()
parser.add_argument('action', choices=['journey', 'readback', 'unavailable'])
args = parser.parse_args()
{'journey': journey, 'readback': readback, 'unavailable': unavailable}[args.action]()
EVIDENCE.mkdir(parents=True, exist_ok=True)
report = {'action': args.action, 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'captured_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'environment': 'ios-accounts local real Supabase auth and Postgres; synthetic users; no hosted/provider calls', 'passed_checks': checks}
(EVIDENCE / f'api-{args.action}.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'{args.action}: {len(checks)} checks passed; sanitized evidence saved')
