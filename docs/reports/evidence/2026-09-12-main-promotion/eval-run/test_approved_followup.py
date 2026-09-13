"""Bounded measurements using the candidate's unchanged harness and fixtures."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path.cwd()
CONTROL = Path(__file__).parent
sys.path.insert(0, str(ROOT))
pytest_plugins = ['tests.conftest']
# Match the native live module's env loading before any Argus import.
from tests.evals import test_measurement_eval_live  # noqa: E402,F401
from tests.evals.measurement_eval_harness import judge_prose_quality, load_eval_cases, run_eval_case  # noqa: E402
from tests.evals.measurement_eval_scorecard import build_scorecard_provenance, validated_provenance_payload  # noqa: E402
from argus.llm.openrouter import begin_openrouter_route_receipt_capture, end_openrouter_route_receipt_capture  # noqa: E402
import promotion_observer  # noqa: E402

SCORECARD = Path('/Users/garces/.codex/worktrees/eca1/private-alpha-next/docs/reports/evidence/2026-09-12-main-promotion/candidate-eval-scorecard-df7aee12.json')
native_bytes = SCORECARD.read_bytes()
native = json.loads(native_bytes)
failures = [row for row in native['results'] if row['status'] == 'failed']
assert len(failures) == 1
failure = failures[0]
case = next(case for case in load_eval_cases() if case.id == failure['id'])

def save(name, data):
    path = CONTROL / name
    assert not path.exists(), 'Refuse to overwrite a measured follow-up'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def test_recorded_judge():
    prose = failure['prose_judge']
    text = prose['judged_assistant_text']
    context = prose['judged_rendered_context']
    assert not text['truncated'] and not context['truncated']
    assert hashlib.sha256(text['text'].encode()).hexdigest() == text['sha256']
    assert hashlib.sha256(context['text'].encode()).hexdigest() == context['sha256']
    promotion_observer.emit({'kind':'approved_followup_start','phase':'recorded_judge','case_id':case.id})
    token = begin_openrouter_route_receipt_capture()
    try:
        result = judge_prose_quality(case=case, assistant_text=text['text'],
                                      rendered_beside_reply=json.loads(context['text']))
    finally:
        receipts = [row.as_dict() for row in end_openrouter_route_receipt_capture(token)]
    save('recorded-judge-replay.json', {'evidence_kind':'recorded_text_judge_replay','case_id':case.id,
         'candidate_sha':native['provenance']['candidate_sha'],'source_scorecard_sha256':hashlib.sha256(native_bytes).hexdigest(),
         'judged_assistant_text_sha256':text['sha256'],'judged_rendered_context_sha256':context['sha256'],
         'recorded_input_unchanged':True,'result':result,'route_receipts':receipts})
    promotion_observer.emit({'kind':'approved_followup_complete','phase':'recorded_judge','case_id':case.id,'judge_pass':result.get('pass')})

def test_case_retry():
    judged = json.loads((CONTROL / 'recorded-judge-replay.json').read_text())
    typed_failures = [check for check in failure['failed_checks'] if not check.startswith('prose_judge:')]
    assert judged['result'].get('pass') is False or typed_failures, 'Case no longer fails; rerun not authorized'
    provenance = build_scorecard_provenance(evaluation_mode='live')
    promotion_observer.emit({'kind':'approved_followup_start','phase':'case_retry','case_id':case.id})
    result = run_eval_case(case)
    save('single-case-rerun.json', {'evidence_kind':'single_case_rerun','case_id':case.id,
         'source_scorecard_sha256':hashlib.sha256(native_bytes).hexdigest(),
         'provenance':validated_provenance_payload(provenance),'result':result,'attempt':1})
    promotion_observer.emit({'kind':'approved_followup_complete','phase':'case_retry','case_id':case.id,'status':result['status']})
    assert result['status'] == 'passed', result['failed_checks']
