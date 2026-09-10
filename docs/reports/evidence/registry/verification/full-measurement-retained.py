"""Run the actual full suite; retain completed OpenRouter responses for fixture diagnosis.

This only wraps the existing HTTP helper and per-case entry point. Requests,
return values, deadlines, schema validation, assertions and grades are unchanged.
No request headers, credentials or conversations outside these fixed eval cases
are recorded. Internal HTTP retries remain owned by the production helper.
"""
from __future__ import annotations

import contextvars
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

repository = Path(sys.argv[1]).resolve(strict=True)
if os.environ.get('ARGUS_RUN_LIVE_EVALS') != '1':
    raise SystemExit('Explicit live opt-in is required')
os.chdir(repository)
sys.path[:0] = [str(repository), str(repository / 'src')]

import pytest
from tests.evals import test_measurement_eval_live as live_suite
from argus.llm import openrouter

assert Path(live_suite.__file__).resolve().is_relative_to(repository)
assert Path(openrouter.__file__).resolve().is_relative_to(repository)
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
active_case = contextvars.ContextVar('registry_eval_case', default=None)
records = repository / 'temp' / f'registry-openrouter-responses-{sha[:8]}.jsonl'
if records.exists():
    raise SystemExit('Refuse to overwrite existing response evidence')
write_lock = threading.Lock()
run_case = live_suite.run_eval_case
post_async = openrouter._post_openrouter_json_schema
post_sync = openrouter._post_openrouter_json_schema_sync


def retain(response, kwargs):
    case_id = active_case.get()
    if response is None or case_id is None:
        return
    request = kwargs.get('payload') or {}
    retry = kwargs.get('retry_attempt') or ()
    try:
        body = response.json()
    except ValueError:
        body = {'unparsed_body': response.text}
    row = {
        'candidate_sha': sha,
        'case_id': case_id,
        'task': retry[0] if retry else None,
        'schema_name': (request.get('response_format') or {}).get('json_schema', {}).get('name'),
        'requested_model': request.get('model'),
        'http_status': response.status_code,
        'response': body,
    }
    with write_lock:
        with records.open('a') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')


async def retained_async(**kwargs):
    response = await post_async(**kwargs)
    retain(response, kwargs)
    return response


def retained_sync(**kwargs):
    response = post_sync(**kwargs)
    retain(response, kwargs)
    return response


def report_case(case):
    token = active_case.set(case.id)
    print(json.dumps({'event': 'case_started', 'case': case.id}), flush=True)
    try:
        result = run_case(case)
        print(json.dumps({
            'event': 'case_completed', 'case': case.id,
            'status': result['status'], 'failed_checks': result['failed_checks'],
        }), flush=True)
        return result
    finally:
        active_case.reset(token)


with pytest.MonkeyPatch.context() as monkeypatch:
    monkeypatch.setattr(openrouter, '_post_openrouter_json_schema', retained_async)
    monkeypatch.setattr(openrouter, '_post_openrouter_json_schema_sync', retained_sync)
    monkeypatch.setattr(live_suite, 'run_eval_case', report_case)
    live_suite.test_measurement_live_eval_suite_writes_scorecard(monkeypatch)
