"""Read-only profiling hooks. No Argus functions, inputs or returns are changed."""
import json
import os
import sys
import threading
import time
from pathlib import Path

SIDE = 'candidate' if 'candidate-eval' in str(Path.cwd()) else 'baseline'
LEDGER = Path('/private/tmp/argus-promotion-20260912-eval-control/events.jsonl')
LOCK = threading.Lock()

def emit(event):
    event.update(side=SIDE, time=time.time())
    with LOCK:
        with LEDGER.open('a') as f:
            f.write(json.dumps(event, separators=(',', ':')) + '\n')

def observe(frame, event, result):
    if event not in ('return', 'call'):
        return
    code = frame.f_code
    name = code.co_name
    if name not in ('record_openrouter_route_receipt', '_usage_from_response', 'search', 'run_eval_case'):
        return
    filename = code.co_filename
    if name == 'run_eval_case' and filename.endswith('/tests/evals/measurement_eval_harness.py'):
        if event == 'call':
            emit({'kind': 'case_start', 'case_id': frame.f_locals['case'].id})
        elif isinstance(result, dict):
            emit({'kind': 'case_complete', 'case_id': result['id'], 'status': result['status'], 'failed_checks': result['failed_checks']})
        return
    if event != 'return':
        return
    if name == 'record_openrouter_route_receipt' and filename.endswith('/argus/llm/openrouter.py') and result is not None:
        emit({'kind': 'cost', 'provider': 'openrouter', 'cost_usd': result.usage_cost_usd, 'outcome': result.outcome, 'task': result.task, 'model': result.model})
    elif name == '_usage_from_response' and filename.endswith('/argus/domain/research/perplexity_agent.py') and result is not None:
        emit({'kind': 'cost', 'provider': 'perplexity_agent', 'cost_usd': result.cost_usd, 'outcome': 'served', 'model': result.model})
    elif name == 'search' and '/argus/domain/research/search/' in filename and result is not None:
        emit({'kind': 'cost', 'provider': result.provider_id, 'cost_usd': result.cost_usd, 'outcome': 'served'})

def pytest_sessionstart(session):
    emit({'kind': 'observer_start', 'python': sys.version.split()[0]})
    sys.setprofile(observe)
    threading.setprofile(observe)

def pytest_sessionfinish(session, exitstatus):
    sys.setprofile(None)
    threading.setprofile(None)
    emit({'kind': 'observer_end', 'exit_status': int(exitstatus)})
