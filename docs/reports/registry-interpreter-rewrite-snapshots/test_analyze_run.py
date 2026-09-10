"""Offline controls for accounting and native-grade integrity; no Argus imports."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import analyze_run as subject


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='registry-analysis-test-', dir='/private/tmp')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.raw = self.base / 'raw'
        self.raw.mkdir()
        inputs = {f'case_{i}': hashlib.sha256(str(i).encode()).hexdigest() for i in range(14)}
        self.preflight = {arm: {'sha': sha, 'clean': True, 'inputs': inputs} for arm, sha in subject.EXPECTED_SHAS.items()}
        self.write('preflight.json', self.preflight)
        self.schedule = []
        for rep in (1, 2):
            for case in inputs:
                for arm in subject.EXPECTED_SHAS:
                    index = len(self.schedule) + 1
                    label = f'{index:02d}-{arm}-r{rep}'
                    self.schedule.append({'index': index, 'repetition': rep, 'arm': arm, 'case': case})
                    self.write(label + '.json', {
                        'artifact_type': 'partial_interleaved_case_probe', 'is_full_suite_scorecard': False,
                        'label': label, 'selected_case_ids': [case], 'case_input_sha256': inputs[case],
                        'provenance': {'candidate_sha': subject.EXPECTED_SHAS[arm], 'worktree_clean': True,
                                       'evaluation_mode': 'live', 'asset_provider_mode': 'live_provider',
                                       'market_data_provider_mode': 'live_provider', 'fixture_sha256': arm},
                        'results': [{'id': case, 'status': 'passed', 'failed_checks': [], 'prose_judge': None,
                                     'typed_outcome': {}, 'route_receipts': []}],
                    })
                    (self.raw / (label + '.responses.jsonl')).write_text('')
        self.write('schedule.json', self.schedule)

    def write(self, name, value):
        (self.raw / name).write_text(json.dumps(value))

    def probe(self, label):
        return json.loads((self.raw / (label + '.json')).read_text())

    def capture(self, label, response_id, cost, **changes):
        item = next(row for row in self.schedule if label == f"{row['index']:02d}-{row['arm']}-r{row['repetition']}")
        row = {'label': label, 'case_id': item['case'], 'candidate_sha': subject.EXPECTED_SHAS[item['arm']],
               'http_status': 200, 'schema_name': None, 'response': {'id': response_id, 'model': 'scripted/model', 'usage': {'cost': cost}}}
        row.update(changes)
        with (self.raw / (label + '.responses.jsonl')).open('a') as stream:
            stream.write(json.dumps(row) + '\n')

    def test_terminal_refuses_missing_output_without_creating_summary(self):
        (self.raw / '56-candidate-r2.json').unlink()
        output = self.base / 'refused'
        command = [sys.executable, str(Path(subject.__file__)), '--input', str(self.raw), '--output', str(output)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('REFUSED_INCOMPLETE', result.stdout)
        self.assertFalse(output.exists())
        partial = subprocess.run(command + ['--partial'], capture_output=True, text=True)
        self.assertEqual(partial.returncode, 0)
        report = json.loads((output / 'analysis.json').read_text())
        self.assertEqual(report['scope'], 'PARTIAL_DIAGNOSTIC_NOT_TERMINAL')
        self.assertEqual(report['readiness']['valid_outputs'], 55)

    def test_captured_rejected_fallback_is_paid_once_separate_from_receipts(self):
        label = '02-candidate-r1'
        for _ in range(2):
            self.capture(label, 'same-provider-response', 0.0292739)
        probe = self.probe(label)
        probe['results'][0]['route_receipts'] = [{'outcome': 'failed', 'failure_mode': 'ValidationError', 'usage_cost_usd': None}]
        self.write(label + '.json', probe)
        report = subject.analyze(self.raw)
        cost = report['cost_accounting']['totals']['candidate']
        self.assertEqual(Decimal(cost['captured_openrouter_known_cost_usd']), Decimal('0.0292739'))
        self.assertEqual(cost['route_receipt_known_cost_usd_separate_not_added'], '0')
        self.assertEqual(cost['unique_captured_response_count'], 1)
        self.assertEqual(Decimal(cost['known_paid_lower_bound_usd']), Decimal('0.0292739'))

    def test_research_cost_survives_zero_invocations_and_duplicate_sidecar(self):
        label = '02-candidate-r1'
        probe = self.probe(label)
        usage = {'cache_status': 'miss', 'invocations': 0, 'cost_usd': 0.09109}
        probe['results'][0]['typed_outcome']['tool_usage'] = [{'call_id': 'a', 'usage': usage}]
        probe['observed_final_research_sidecar'] = {'usage': deepcopy(usage)}
        self.write(label + '.json', probe)
        cost = subject.analyze(self.raw)['cost_accounting']['totals']['candidate']
        self.assertEqual(Decimal(cost['research_known_new_spend_usd']), Decimal('0.09109'))

    def test_repeated_tools_distinct_calls_count_once_each_cache_hit_excluded(self):
        label = '02-candidate-r1'
        probe = self.probe(label)
        usage = {'cache_status': 'miss', 'invocations': 1, 'cost_usd': 0.005}
        probe['results'][0]['typed_outcome']['tool_usage'] = [
            {'call_id': 'a', 'tool_name': 'research', 'usage': usage},
            {'call_id': 'a', 'tool_name': 'research', 'usage': deepcopy(usage)},
            {'call_id': 'b', 'tool_name': 'research', 'usage': usage},
            {'call_id': 'c', 'tool_name': 'research', 'usage': {**usage, 'cache_status': 'hit'}},
        ]
        self.write(label + '.json', probe)
        costs = subject.analyze(self.raw)['cost_accounting']
        self.assertEqual(Decimal(costs['totals']['candidate']['research_known_new_spend_usd']), Decimal('0.010'))

    def test_baseline_sidecar_and_unknown_timeouts_remain_distinct(self):
        label = '01-baseline-r1'
        probe = self.probe(label)
        probe['observed_final_research_sidecar'] = {'usage': {'cache_status': 'miss', 'cost_usd': 0.005, 'invocations': 1}}
        probe['results'][0]['route_receipts'] = [{'outcome': 'failed', 'failure_mode': 'TimeoutError', 'usage_cost_usd': None}]
        self.write(label + '.json', probe)
        costs = subject.analyze(self.raw)['cost_accounting']
        self.assertEqual(Decimal(costs['totals']['baseline']['known_paid_lower_bound_usd']), Decimal('0.005'))
        self.assertTrue(costs['additional_cost_unknown'])
        self.assertIn('timed_out_request_cost_unknown', [row['reason'] for row in costs['unresolved_cost_evidence']])

    def test_grade_contradictions_flag_acceptance_without_regrading(self):
        for label, grade, criteria, status in [('01-baseline-r1', False, [], 'passed'), ('02-candidate-r1', True, ['honesty'], 'failed')]:
            probe = self.probe(label)
            probe['results'][0].update(status=status, prose_judge={'pass': grade, 'failed_criteria': criteria})
            self.write(label + '.json', probe)
        report = subject.analyze(self.raw)
        self.assertTrue(report['readiness']['terminal_summary_allowed'])
        self.assertFalse(report['acceptance_grade_integrity']['valid'])
        self.assertEqual(len(report['acceptance_grade_integrity']['invalid_native_grades']), 2)
        pair = next(row for row in report['comparison'] if row['case'] == 'case_0' and row['repetition'] == 1)
        self.assertEqual(pair['arms']['baseline']['status'], 'passed')
        self.assertEqual(pair['arms']['candidate']['status'], 'failed')
        self.assertFalse(pair['pair_acceptance_grade_valid'])
        self.assertFalse(pair['same_fixture_sha256'])

    def test_manifest_and_human_annotation_do_not_mutate_inputs(self):
        original = {path.name: path.read_bytes() for path in self.raw.iterdir()}
        report = subject.analyze(self.raw, review_notes={'01-baseline-r1': {'note': 'Human note; retain grade.'}})
        self.assertEqual(original, {path.name: path.read_bytes() for path in self.raw.iterdir()})
        for name, raw in original.items():
            self.assertEqual(report['provenance']['source_manifest'][name]['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertTrue(report['readiness']['terminal_summary_allowed'])

    def test_provenance_mismatch_refuses_terminal(self):
        label = '02-candidate-r1'
        probe = self.probe(label)
        probe['provenance']['candidate_sha'] = 'wrong'
        self.write(label + '.json', probe)
        report = subject.analyze(self.raw)
        self.assertFalse(report['readiness']['terminal_summary_allowed'])
        self.assertIn('frozen_sha', ' '.join(report['readiness']['problems']))


if __name__ == '__main__':
    unittest.main()
