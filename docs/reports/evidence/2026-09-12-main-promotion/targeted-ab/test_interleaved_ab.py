"""One native targeted measurement per process, with unchanged live fixtures."""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
CONTROL = Path(__file__).parent
sys.path.insert(0, str(ROOT))
pytest_plugins = ['tests.conftest']
from tests.evals import test_measurement_eval_live as live  # noqa: E402
from tests.evals.measurement_eval_harness import load_eval_cases, run_eval_case  # noqa: E402
from tests.evals.measurement_eval_scorecard import build_scorecard_provenance, validated_provenance_payload, assert_provenance_matches_current_run  # noqa: E402
from argus.domain.market_data.assets import clear_asset_cache  # noqa: E402
import pytest  # noqa: E402
import promotion_observer  # noqa: E402

CASE_ID = 'messy_spanish_future_performance_nvda_cruce_dorado'
SIDE = promotion_observer.SIDE

@pytest.mark.parametrize('attempt', range(1, 11))
def test_targeted_case(attempt):
    live._assert_requested_live_eval_credentials()
    clear_asset_cache()
    case = next(case for case in load_eval_cases() if case.id == CASE_ID)
    targeted_hash = hashlib.sha256(json.dumps(case.raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    provenance = build_scorecard_provenance(evaluation_mode='live')
    assert all(str(Path(module.__file__).resolve()).startswith(str(ROOT) + '/')
               for name, module in sys.modules.items()
               if name.startswith('argus') and getattr(module, '__file__', None))
    started = time.time()
    promotion_observer.emit({'kind': 'targeted_ab_start', 'attempt': attempt, 'case_id': CASE_ID})
    result = run_eval_case(case)
    assert_provenance_matches_current_run(provenance)
    research = (result.get('typed_outcome') or {}).get('research') or {}
    timeout = research.get('degraded_code') == 'research_unavailable_timeout'
    failed = timeout or result['status'] != 'passed'
    report = {'scorecard_kind': 'live_targeted_interleaved_ab_attempt', 'case_id': CASE_ID,
              'side': SIDE, 'attempt': attempt, 'started_at_epoch': started,
              'finished_at_epoch': time.time(), 'provenance': validated_provenance_payload(provenance),
              'targeted_case_sha256': targeted_hash, 'native_case': case.raw,
              'argus_imports_local': True, 'result': result,
              'measurement': {'failed': failed, 'research_timeout': timeout,
                  'classification': 'Any native non-pass or research timeout is a failed attempt. No attempt is discarded.'}}
    path = CONTROL / 'targeted-ab' / f'attempt-{attempt:02d}-{SIDE}.json'
    with path.open('x') as output:
        output.write(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    promotion_observer.emit({'kind': 'targeted_ab_complete', 'attempt': attempt,
                            'case_id': CASE_ID, 'failed': failed, 'research_timeout': timeout})
