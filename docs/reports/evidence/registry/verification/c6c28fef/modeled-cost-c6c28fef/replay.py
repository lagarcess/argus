"""Replay one retained primary reply; sockets and new provider work are forbidden."""

import asyncio
import json
import os
import socket
from pathlib import Path
from unittest.mock import patch

ROOT = Path('/Users/garces/.codex/worktrees/aa72/private-alpha-next')
OUT = Path(__file__).parent
CASE = 'natural_language_establishes_modeled_costs_issue_271'
os.environ['ARGUS_RESEARCH_RAIL_ENABLED'] = 'false'
os.environ['ARGUS_ENABLE_PERSONALIZATION_MEMORY'] = 'false'
os.environ['ARGUS_MARKET_DATA_PROVIDER_MODE'] = 'synthetic_unit_fixture'
os.environ['ARGUS_ENABLE_EXECUTION_REALISM'] = 'true'


def no_network(*args, **kwargs):
    raise AssertionError('Network is forbidden in this retained-response replay')


async def main():
    from loguru import logger
    logger.remove()
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.capabilities.contract import build_default_capability_contract
    from argus.agent_runtime.graph import workflow
    from argus.agent_runtime.interpreter.execution_cost_capability import has_execution_cost_candidate
    from argus.agent_runtime.interpreter.strategy_builder import _strategy_from_llm
    from argus.agent_runtime.interpreter.strategy_routing import strategy_route_expected
    from argus.agent_runtime.runtime import build_workflow_input
    from argus.agent_runtime.stages import confirm
    from argus.agent_runtime.stages.interpret_types import InterpretationRequest
    from argus.agent_runtime.state.models import UserState
    from langgraph.checkpoint.memory import MemorySaver
    import yaml

    records = []
    for line in (ROOT/'temp/registry-openrouter-responses-c6c28fef.jsonl').read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('case_id') == CASE:
            content = row['response']['choices'][0]['message']['content']
            records.append((row['schema_name'], json.loads(content)))
    primary = next(body for name, body in records if name == 'LLMInterpretationResponse')
    (OUT/'primary.json').write_text(json.dumps(primary, indent=2)+'\n')
    fixtures = yaml.safe_load((ROOT/'tests/evals/measurement_cases/action_chip_semantics.yaml').read_text())
    message = next(case['prompt'] for case in fixtures['cases'] if case['id'] == CASE)
    assert message == primary['user_goal_summary']
    user = UserState(user_id='retained-cost-replay')
    request = InterpretationRequest(current_user_message=message, user=user)
    interpreter = llm_interpreter.OpenRouterStructuredInterpreter(contract=build_default_capability_contract())
    parsed = interpreter.response_model.model_validate(primary)
    draft = parsed.candidate_strategy_draft
    original_gate = llm_interpreter._response_needs_stated_run_field_fidelity_audit
    observations = {
        'case_id': CASE,
        'message_from_unchanged_fixture': True,
        'primary_intent': parsed.intent,
        'primary_act': parsed.semantic_turn_act,
        'primary_tool_calls': len(parsed.tool_calls),
        'primary_typed_costs': {'fee_rate': draft.fee_rate, 'slippage': draft.slippage},
        'primary_extra_costs': {name: draft.extra_parameters.get(name) for name in ('fee_rate','slippage')},
        'strategy_route_expected': strategy_route_expected(intent=parsed.intent, semantic_turn_act=parsed.semantic_turn_act),
        'cost_candidate_seen': has_execution_cost_candidate(draft.extra_parameters),
        'fidelity_audit_eligible': original_gate(response=parsed, request=request),
    }
    canonical = _strategy_from_llm(draft, request.current_user_message)
    observations['canonical_without_audit'] = {name: canonical.extra_parameters.get(name) for name in ('fee_rate','slippage')}

    def route_applicability_control(*, response, request=None):
        # Predicate-only control. The primary response and its intent remain unchanged.
        if response.intent in {'explain', 'follow_up'} and strategy_route_expected(
            intent=response.intent, semantic_turn_act=response.semantic_turn_act
        ):
            response = response.model_copy(update={'intent':'calculate'})
        return original_gate(response=response, request=request)

    async def replay(control):
        schema_calls = []

        async def recorded_reply(*, schema_name, schema_model, **kwargs):
            schema_calls.append(schema_name)
            if control and schema_name == 'StatedRunFieldFidelityAudit':
                # Controlled sidecar outcome, not a retained live provider response.
                return schema_model.model_validate({
                    'fee': {'rate':0.001, 'evidence_span':'10 bps fee'},
                    'slippage': {'rate':0.0005, 'evidence_span':'5 bps slippage'},
                    'confidence':0.98,
                })
            matches = [body for name, body in records if name == schema_name]
            if len(matches) != 1:
                raise AssertionError(f'No unique recorded provider response for {schema_name}')
            return schema_model.model_validate(matches[0])

        gate = route_applicability_control if control else original_gate
        with patch.object(llm_interpreter,'invoke_openrouter_json_schema',recorded_reply), patch.object(confirm,'_market_clock_for_strategy',lambda _:None), patch.object(llm_interpreter,'_response_needs_stated_run_field_fidelity_audit',gate):
            graph = workflow.build_workflow(tool=object(),structured_interpreter=interpreter,checkpointer=MemorySaver())
            result = await graph.ainvoke(
                build_workflow_input(user=user,message=request.current_user_message),
                {'configurable':{'thread_id':f'retained-modeled-cost-c6c28fef-{control}'}},
            )
        state = result['run_state']
        payload = state.confirmation_payload
        if hasattr(payload,'model_dump'):
            payload=payload.model_dump(mode='json')
        assert 'launch_payload' in (payload or {})
        launch = payload['launch_payload']
        return {
            'controlled_applicability_and_sidecar':control,
            'schema_calls':schema_calls,
            'final_intent':state.intent,
            'final_stage':str(result['stage_outcome']),
            'final_costs':{name:state.candidate_strategy_draft.extra_parameters.get(name) for name in ('fee_rate','slippage')},
            'final_cost_provenance':{name:state.candidate_strategy_draft.extra_parameters.get('field_provenance',{}).get(name) for name in ('fee_rate','slippage')},
            'launch_execution_realism':launch.get('_execution_realism'),
            'has_real_launch_payload':True,
        }

    observations['original'] = await replay(False)
    observations['applicability_control'] = await replay(True)
    (OUT/'result.json').write_text(json.dumps(observations,indent=2,default=str)+'\n')
    print(json.dumps(observations,indent=2,default=str))
    assert observations['primary_typed_costs']=={'fee_rate':0.001,'slippage':0.0005}
    assert observations['strategy_route_expected']
    assert not observations['fidelity_audit_eligible']
    original=observations['original']
    # Synthetic asset resolution skips preflight; the exact primary response is unchanged.
    assert original['schema_calls']==['LLMInterpretationResponse']
    assert original['final_stage']=='WorkflowStageOutcome.AWAIT_APPROVAL'
    assert original['final_costs']=={'fee_rate':None,'slippage':None}
    assert original['launch_execution_realism'] is None
    control=observations['applicability_control']
    assert control['schema_calls']==['LLMInterpretationResponse','StatedRunFieldFidelityAudit']
    assert control['final_stage']=='WorkflowStageOutcome.AWAIT_APPROVAL'
    assert control['final_costs']=={'fee_rate':0.001,'slippage':0.0005}
    assert control['final_cost_provenance']=={'fee_rate':'explicit_user','slippage':'explicit_user'}
    assert control['launch_execution_realism']=={'enabled':True,'fee_bps':10.0,'slippage_bps':5.0}


with patch.object(socket.socket,'connect',no_network), patch.object(socket.socket,'connect_ex',no_network), patch.object(socket,'create_connection',no_network):
    asyncio.run(main())
