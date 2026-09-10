"""Interleave all fourth-run failures and three passing controls, without regrading."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import yaml

CASES = (
    'natural_language_establishes_modeled_costs_issue_271',
    'asset_discovery_comparison_anchor_english_issue_244',
    'asset_discovery_category_spanish_issue_244',
    'asset_discovery_recent_ipo_exact_issue_344',
    'asset_discovery_trending_crypto_exact_issue_344',
    'asset_discovery_not_result_followup_issue_244',
    'metric_correctness_eth_default_crypto_benchmark',
    'capability_honesty_news_sentiment_rule_aapl',
    'dca_capital_semantics_only_have_amount_is_ceiling_issue_455',
    'dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run',
    'dca_capital_semantics_prebaked_chip_spanish_pesos_reaches_ready_to_run',
    'capability_honesty_golden_cross_control_aapl',
    'messy_english_post_result_fact_then_capital_edit_issue_160',
    'ordinary_conversation_concept_inflation_es',
)


def preflight(repository):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repository, text=True).strip()
    if git('status', '--porcelain'):
        raise SystemExit(f'Refuse dirty measured checkout: {repository}')
    cases = {}
    for path in sorted((repository / 'tests/evals/measurement_cases').glob('*.yaml')):
        for case in yaml.safe_load(path.read_text())['cases']:
            if case['id'] in CASES:
                inputs = {key: value for key, value in case.items()
                          if key not in {'expected', 'expected_fail', 'prose_judge'}}
                cases[case['id']] = hashlib.sha256(json.dumps(
                    inputs, sort_keys=True, separators=(',', ':'), default=str
                ).encode()).hexdigest()
    assert set(cases) == set(CASES)
    return {'sha': git('rev-parse', 'HEAD'), 'clean': True, 'inputs': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    proof = {arm: preflight(getattr(args, arm)) for arm in ('baseline', 'candidate')}
    assert proof['baseline']['inputs'] == proof['candidate']['inputs']
    schedule = [
        {'repetition': rep + 1, 'case': case, 'arm': arm}
        for rep in range(2)
        for index, case in enumerate(CASES)
        for arm in (('baseline', 'candidate') if (rep + index) % 2 == 0
                    else ('candidate', 'baseline'))
    ]
    for index, row in enumerate(schedule, 1):
        row['index'] = index
    if args.dry_run:
        print(json.dumps({'preflight': proof, 'schedule': schedule}, indent=2))
        return
    if os.getenv('ARGUS_RUN_LIVE_EVALS') != '1':
        raise SystemExit('Live opt-in required')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'preflight.json').write_text(json.dumps(proof, indent=2) + '\n')
    (args.output / 'schedule.json').write_text(json.dumps(schedule, indent=2) + '\n')
    env = {
        **os.environ, 'ARGUS_RUN_LIVE_EVALS': '1',
        'ARGUS_EVAL_ENV_FILE': str(args.candidate / '.env'),
        'ARGUS_RESEARCH_RAIL_ENABLED': 'true',
        'ARGUS_MARKET_DATA_PROVIDER_MODE': 'live_provider',
        'ARGUS_ASSET_PROVIDER_MODE': 'live_provider',
        'ARGUS_ENABLE_PERSONALIZATION_MEMORY': 'false',
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1',
    }
    for row in schedule:
        label = f"{row['index']:02d}-{row['arm']}-r{row['repetition']}"
        output = args.output / f'{label}.json'
        print(json.dumps({'started': row}), flush=True)
        command = [
            str(args.candidate / '.venv/bin/python'),
            str(Path(__file__).with_name('retained-case-probe.py')),
            '--repository', str(getattr(args, row['arm'])),
            '--environment', str(args.candidate / '.env'),
            '--case', row['case'], '--label', label, '--output', str(output),
        ]
        with output.with_suffix('.log').open('x') as log:
            completed = subprocess.run(command, env=env, stdout=log, stderr=log)
        if completed.returncode:
            raise SystemExit(f'{label} exited {completed.returncode}; stop and inspect')
        measured = json.loads(output.read_text())
        assert measured['provenance']['candidate_sha'] == proof[row['arm']]['sha']
        assert measured['case_input_sha256'] == proof[row['arm']]['inputs'][row['case']]
        result = measured['results'][0]
        print(json.dumps({'completed': label, 'case': row['case'],
                          'status': result['status'], 'failed_checks': result['failed_checks'],
                          'provider_usage': measured['provider_usage']}), flush=True)
    print('Partial interleaved measurement completed; this is not a full-suite scorecard.', flush=True)


if __name__ == '__main__':
    main()
