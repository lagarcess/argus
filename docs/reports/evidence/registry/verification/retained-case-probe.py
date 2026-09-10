"""Run one unchanged native case and retain replies without changing its grade."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True, type=Path)
    parser.add_argument('--environment', required=True, type=Path)
    parser.add_argument('--case', required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if os.getenv('ARGUS_RUN_LIVE_EVALS') != '1':
        raise SystemExit('Live opt-in required; this command spends provider tokens')
    responses_path = args.output.with_suffix('.responses.jsonl')
    if args.output.exists() or responses_path.exists():
        raise SystemExit('Refuse to overwrite prior evidence')
    repository = args.repository.resolve(strict=True)
    os.chdir(repository)
    sys.path[:0] = [str(repository), str(repository / 'src')]
    from dotenv import load_dotenv
    load_dotenv(args.environment, override=False)
    from argus.llm import openrouter
    from tests.evals import measurement_eval_harness as harness
    from tests.evals import measurement_eval_scorecard as scorecards
    for module in (openrouter, harness, scorecards):
        assert Path(module.__file__).resolve().is_relative_to(repository)
    case = next(case for case in harness.load_eval_cases() if case.id == args.case)
    provenance = scorecards.build_scorecard_provenance(evaluation_mode='live')
    inputs = {key: value for key, value in case.raw.items()
              if key not in {'expected', 'expected_fail', 'prose_judge'}}
    input_digest = hashlib.sha256(json.dumps(
        inputs, sort_keys=True, separators=(',', ':'), default=str
    ).encode()).hexdigest()
    post_async = openrouter._post_openrouter_json_schema
    post_sync = openrouter._post_openrouter_json_schema_sync
    final_patch = harness._final_patch
    observed_research = None
    lock = threading.Lock()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def retain(response, kwargs):
        if response is None:
            return
        request = kwargs.get('payload') or {}
        retry = kwargs.get('retry_attempt') or ()
        schema = (request.get('response_format') or {}).get('json_schema', {}).get('name')
        try:
            body = response.json()
        except ValueError:
            body = {'unparsed_body': response.text}
        row = {
            'candidate_sha': provenance.candidate_sha, 'case_id': case.id,
            'label': args.label, 'task': retry[0] if retry else None,
            'schema_name': schema, 'requested_model': request.get('model'),
            'http_status': response.status_code, 'response': body,
        }
        if schema == 'ArgusProseJudgeResponse':
            row['judge_request_payload'] = request
        with lock, responses_path.open('a') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')

    async def retained_async(**kwargs):
        response = await post_async(**kwargs)
        retain(response, kwargs)
        return response

    def retained_sync(**kwargs):
        response = post_sync(**kwargs)
        retain(response, kwargs)
        return response

    def retained_patch(*args, **kwargs):
        nonlocal observed_research
        patch = final_patch(*args, **kwargs)
        if isinstance(patch.get('research'), dict):
            observed_research = copy.deepcopy(patch['research'])
        return patch

    openrouter._post_openrouter_json_schema = retained_async
    openrouter._post_openrouter_json_schema_sync = retained_sync
    harness._final_patch = retained_patch
    started_at = datetime.now(timezone.utc).isoformat()
    started = monotonic()
    try:
        result = harness.run_eval_case(case)
    finally:
        openrouter._post_openrouter_json_schema = post_async
        openrouter._post_openrouter_json_schema_sync = post_sync
        harness._final_patch = final_patch
    scorecards.assert_provenance_matches_current_run(provenance)
    payload = {
        'artifact_type': 'partial_interleaved_case_probe',
        'is_full_suite_scorecard': False, 'label': args.label,
        'started_at': started_at, 'elapsed_seconds': monotonic() - started,
        'provenance': scorecards.validated_provenance_payload(provenance),
        'case_input_sha256': input_digest, 'selected_case_ids': [case.id],
        'provider_usage': scorecards._provider_usage([result]), 'results': [result],
        'observed_final_research_sidecar': observed_research,
    }
    with args.output.open('x') as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'label': args.label, 'case': case.id, 'status': result['status'],
                      'failed_checks': result['failed_checks'],
                      'elapsed_seconds': payload['elapsed_seconds']}), flush=True)


if __name__ == '__main__':
    main()
