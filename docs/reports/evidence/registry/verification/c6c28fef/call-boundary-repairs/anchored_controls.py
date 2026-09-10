import asyncio
import contextlib
import io
import json
import runpy

with contextlib.redirect_stdout(io.StringIO()):
    env = runpy.run_path('/private/tmp/registry-benchmark-diagnosis/replay.py')

from argus.agent_runtime.interpreter import backtest_calls
from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
from argus.agent_runtime.resolution import resolve_asset_candidate
from argus.agent_runtime.run_field_contract import field_fidelity_tokens, _contains_ordered_token_span
from argus.agent_runtime.stages import interpret
from argus.agent_runtime.stages.confirm import confirm_stage
from argus.agent_runtime.capabilities.contract import build_default_capability_contract

before, captured_after, request = env['observed'][0]


def project(response, request):
    strategy = _strategy_from_llm(response.candidate_strategy_draft, request.current_user_message)
    resolution = resolve_asset_candidate(strategy.comparison_baseline, field='comparison_baseline', source='llm_extraction', asset_class_hint=strategy.asset_class)
    strategy, codes = interpret._strategy_with_validated_benchmark_symbol(strategy)
    strategy, default_codes = interpret._strategy_with_default_benchmark(strategy)
    return strategy, resolution, codes + default_codes


def source_bound(response, prior, request):
    draft = response.candidate_strategy_draft
    span = str(draft.evidence_spans.get('comparison_baseline') or '').strip()
    value = str(draft.comparison_baseline or '').strip()
    # The existing call-source owner has already bounded request.current_user_message.
    # This is provenance only, not a semantic parser or a ticker alias.
    tokens = field_fidelity_tokens(value.casefold())
    prior_span = str(prior.candidate_strategy_draft.evidence_spans.get('comparison_baseline') or '').strip()
    return bool(span and prior_span and tokens and span in request.current_user_message and prior_span in request.current_user_message and _contains_ordered_token_span(field_fidelity_tokens(span.casefold()), tokens) and _contains_ordered_token_span(field_fidelity_tokens(prior_span.casefold()), tokens))

async def run():
    for label, value, span, source, prior_value, change_date in [
        ('captured', 'default crypto benchmark', 'against the default crypto benchmark', None, 'BTC', False),
        ('canonical_alias', 'BTCUSD', 'against the default crypto benchmark', None, 'BTC', False),
        ('different_canonical', 'ETH', 'ethereum', None, 'BTC', False),
        ('invented_value_real_quote', 'Samsung', 'against the default crypto benchmark', None, 'BTC', False),
        ('invented_value_invented_quote', 'Samsung', 'Samsung', None, 'BTC', False),
        ('incidental_other_field_mention', 'Samsung', 'Samsung', request.current_user_message + '; Samsung is unrelated background.', 'BTC', False),
        ('unbound_quote', 'default crypto benchmark', 'against a default crypto benchmark', None, 'BTC', False),
        ('missing_quote', 'default crypto benchmark', '', None, 'BTC', False),
        ('other_call_scope', 'default crypto benchmark', 'against the default crypto benchmark', 'Backtest Ethereum from 2024-01-01 to 2024-03-31', 'BTC', False),
        ('reconciliation_changes_supplied_benchmark', 'default crypto benchmark', 'against the default crypto benchmark', None, 'ETH', False),
        ('other_fact_still_conflicts', 'default crypto benchmark', 'against the default crypto benchmark', None, 'BTC', True),
    ]:
        old = before.model_copy(deep=True)
        old.candidate_strategy_draft.comparison_baseline = prior_value
        after = captured_after.model_copy(deep=True)
        after.candidate_strategy_draft.comparison_baseline = value
        after.candidate_strategy_draft.evidence_spans['comparison_baseline'] = span
        if change_date:
            after.candidate_strategy_draft.date_range_intent.end = '2024-04-30'
        scoped = request.model_copy(update={'current_user_message': source}) if source is not None else request
        old_strategy, old_resolution, _ = project(old, scoped)
        new_strategy, new_resolution, codes = project(after, scoped)
        same_resolved_identity = (old_resolution.status == new_resolution.status == 'resolved' and old_resolution.asset == new_resolution.asset)
        disclosed_reconciliation = bool(
            old_resolution.status == 'resolved'
            and new_resolution.status in {'unsupported', 'ambiguous'}
            and source_bound(after, old, scoped)
            and new_strategy.comparison_baseline == old_strategy.comparison_baseline
            and any(p.field == 'comparison_baseline' and p.resolution_status == new_resolution.status and p.raw_text.casefold() == value.casefold() for p in new_strategy.resolution_provenance)
        )
        conflicts = backtest_calls._known_input_conflicts(old, after, request=scoped)
        conflicts = [c for c in conflicts if not (c.field_name == 'comparison_baseline' and (same_resolved_identity or disclosed_reconciliation))]
        if conflicts:
            proposed = old.model_copy(deep=True)
            proposed.ambiguous_fields.extend(conflicts)
            proposed.requires_clarification = True
        else:
            proposed = after
        prepared = await backtest_calls._prepared_stage(proposed, request=scoped, state=env['state'])
        result = {'case':label, 'disposition':'provider_equivalent' if same_resolved_identity else 'disclosed_reconciliation' if disclosed_reconciliation else 'conflict', 'conflicts':[c.field_name for c in conflicts], 'outcome':prepared.outcome}
        if label == 'captured':
            ready_state = env['state'].model_copy(update={'candidate_strategy_draft': prepared.decision.candidate_strategy_draft, 'optional_parameter_status': prepared.patch.get('optional_parameter_status', {})})
            confirmed = confirm_stage(state=ready_state, contract=build_default_capability_contract())
            payload = confirmed.patch.get('confirmation_payload', {})
            result['confirmation_outcome'] = confirmed.outcome
            result['confirmation_benchmark'] = payload.get('launch_payload', {}).get('benchmark_symbol')
            result['confirmation_provenance'] = [p for p in payload.get('strategy', {}).get('resolution_provenance', []) if p.get('field') == 'comparison_baseline']
        expected = 'ready_for_confirmation' if label in {'captured', 'canonical_alias'} else 'needs_clarification'
        assert prepared.outcome == expected, result
        if label == 'captured':
            assert result['confirmation_outcome'] == 'await_approval', result
            assert result['confirmation_benchmark'] == 'BTC', result
            assert result['confirmation_provenance'][0]['resolution_status'] == 'unsupported', result
        print(json.dumps(result))

asyncio.run(run())
