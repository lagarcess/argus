"""Replay this case's actual selected call and sidecars, with sockets forbidden."""
import asyncio
import json
import os
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack

ROOT=Path('/Users/garces/.codex/worktrees/aa72/private-alpha-next')
OUT=Path(__file__).parent
CASE='dca_capital_semantics_prebaked_chip_bare_amount_reaches_ready_to_run'
CONTROL='--scope-control' in sys.argv
os.environ['ARGUS_RESEARCH_RAIL_ENABLED']='false'
os.environ['ARGUS_ENABLE_PERSONALIZATION_MEMORY']='false'
os.environ['ARGUS_MARKET_DATA_PROVIDER_MODE']='synthetic_unit_fixture'
os.environ['ARGUS_ENABLE_EXECUTION_REALISM']='true'

def forbidden(*args, **kwargs):
    raise AssertionError('Network forbidden in this replay')

@dataclass(frozen=True)
class Asset:
    canonical_symbol:str
    asset_class:str='equity'
    name:str=''
    raw_symbol:str=''

async def main():
    from loguru import logger
    logger.remove()
    import yaml
    from argus.agent_runtime import llm_interpreter
    from argus.agent_runtime.backtest_input import BacktestStrategyInput
    from argus.agent_runtime.interpreter import backtest_calls
    from argus.agent_runtime.stages import interpret
    from argus.agent_runtime.state.models import RunState,TaskSnapshot,UserState
    from argus.domain.tool_contracts import ToolCall

    records=[]
    for line_number,line in enumerate((ROOT/'temp/registry-openrouter-responses-c6c28fef.jsonl').read_text().splitlines(),1):
        try: row=json.loads(line)
        except ValueError: continue
        if row.get('case_id') != CASE: continue
        body=row['response']['choices'][0]['message']['content'].strip()
        if body.startswith('```'):
            body='\n'.join(body.splitlines()[1:-1])
        records.append({'line':line_number,'schema':row.get('schema_name'),'body':json.loads(body)})
    primary=next(row for row in records if row['schema']=='LLMInterpretationResponse' and row['body'].get('tool_calls'))
    call=ToolCall.model_validate(primary['body']['tool_calls'][0])
    (OUT/'primary.json').write_text(json.dumps(primary,indent=2)+'\n')
    actual_audits=[row for row in records if row['line']>primary['line'] and row['schema']!='ClarificationResponse']
    assert [row['schema'] for row in actual_audits]==[
        'AssetGroundingAudit','DcaContractAudit',None,'StrategyFamilyContinuityAudit',
        'DcaContributionRoleAudit','StatedRunFieldFidelityAudit'
    ]
    # Fallback DcaContractAudit is the retained successful fenced-JSON body.
    actual_audits[2]['schema']='DcaContractAudit'
    raw_cases=yaml.safe_load((ROOT/'tests/evals/measurement_cases/dca_capital_semantics.yaml').read_text())['cases']
    fixture=next(case for case in raw_cases if case['id']==CASE)
    snapshot_payload=dict(fixture['snapshot'])
    snapshot_payload['pending_strategy_summary']=snapshot_payload.pop('pending_strategy')
    snapshot=TaskSnapshot.model_validate(snapshot_payload)
    first_clarifier=next(row['body'] for row in records if row['schema']=='ClarificationResponse')
    state=RunState(
        current_user_message=fixture['followup_prompt'],
        recent_thread_history=[{'role':'assistant','content':first_clarifier['question']}],
        intent=primary['body']['intent'],task_relation=primary['body']['task_relation'],
        semantic_turn_act=primary['body']['semantic_turn_act'],tool_calls=[call],
        user_goal_summary=primary['body']['user_goal_summary'],
    )
    metadata={'last_stage_outcome':'await_user_reply','requested_field':'capital_amount'}
    events=[]
    calls=[]
    def facts(response):
        draft=response.candidate_strategy_draft
        return {
            'intent':response.intent,'act':response.semantic_turn_act,'relation':response.task_relation,
            'assets':draft.asset_universe,'capital_amount':draft.capital_amount,
            'recurring_contribution':draft.recurring_contribution,'missing':response.missing_required_fields,
            'requires_clarification':response.requires_clarification,
            'ambiguities':[item.model_dump(mode='json') for item in response.ambiguous_fields],
            'reason_codes':response.reason_codes,
        }
    async def replay_provider(*,schema_name,schema_model,**kwargs):
        index=len(calls)
        if index>=len(actual_audits): raise AssertionError(f'Unexpected provider request {schema_name}')
        row=actual_audits[index]
        assert row['schema']==schema_name,(index,schema_name,row['schema'])
        calls.append({'schema':schema_name,'retained_line':row['line']})
        return schema_model.model_validate(row['body'])
    def resolver(symbol,**kwargs):
        if symbol.upper() in {'KO','CCEP'}: return Asset(symbol.upper())
        return original_resolver(symbol,**kwargs)
    original_resolver=llm_interpreter.resolve_asset
    def observe_stage(name,original):
        async def observed(*args,**kwargs):
            response=kwargs.get('response') if 'response' in kwargs else args[0]
            before=facts(response)
            result=await original(*args,**kwargs)
            after=facts(result) if hasattr(result,'candidate_strategy_draft') else None
            events.append({'owner':name,'before':before,'after':after})
            return result
        return observed
    original_conflicts=backtest_calls._known_input_conflicts
    def observe_conflicts(*args,**kwargs):
        before, after = args
        scope_before = {'before':facts(before),'after':facts(after)}
        if CONTROL:
            # Same scope restoration production already promises, moved before comparison.
            after.intent=before.intent
            after.task_relation=before.task_relation
            after.semantic_turn_act=before.semantic_turn_act
        conflicts=original_conflicts(*args,**kwargs)
        events.append({'owner':'known_input_conflicts','scope_control':CONTROL,'inputs':scope_before,'conflicts':[item.model_dump(mode='json') for item in conflicts]})
        return conflicts
    with ExitStack() as stack:
        stack.enter_context(patch.object(llm_interpreter,'invoke_openrouter_json_schema',replay_provider))
        for module in (llm_interpreter,interpret): stack.enter_context(patch.object(module,'resolve_asset',resolver))
        for name in ('_asset_grounding_audited_response','_dca_contract_audited_response','_dca_contribution_role_audited_response'):
            stack.enter_context(patch.object(llm_interpreter,name,observe_stage(name,getattr(llm_interpreter,name))))
        stack.enter_context(patch.object(backtest_calls,'_prepared_stage',observe_stage('_prepared_stage',backtest_calls._prepared_stage)))
        stack.enter_context(patch.object(backtest_calls,'_known_input_conflicts',observe_conflicts))
        result=await backtest_calls.prepare_backtest_tool_input(
            BacktestStrategyInput.model_validate(call.arguments['strategy']),state=state,
            user=UserState(user_id='retained-prebaked-dca'),latest_task_snapshot=snapshot,
            selected_thread_metadata=metadata,call=call,
        )
    output={
        'case_id':CASE,'scope_control':CONTROL,'actual_call_id':call.call_id,
        'context_note':'Existing fixture KO snapshot and actual first clarification; pending amount metadata follows that clarification.',
        'snapshot_assets':snapshot.pending_strategy_summary.asset_universe,
        'actual_initial_clarification':first_clarifier,
        'calls':calls,'events':events,'outcome':result.outcome,'patch':result.patch,
    }
    (OUT/('scope-control.json' if CONTROL else 'result.json')).write_text(json.dumps(output,indent=2,default=str)+'\n')
    print(json.dumps({key:value for key,value in output.items() if key not in {'patch','actual_initial_clarification'}},indent=2,default=str))
    strategy=result.patch.get('candidate_strategy_draft',{})
    print(json.dumps({'final_strategy_assets':strategy.get('asset_universe'),'final_capital':strategy.get('capital_amount'),'final_recurring':strategy.get('extra_parameters',{}).get('recurring_contribution'),'missing':result.patch.get('missing_required_fields'),'optional_status':result.patch.get('optional_parameter_status'),'requested_field':result.patch.get('requested_field')},indent=2,default=str))
    assert strategy['asset_universe']==['KO']
    assert strategy['capital_amount']==200
    conflict_event=next(event for event in events if event['owner']=='known_input_conflicts')
    if CONTROL:
        assert conflict_event['conflicts']==[]
        assert result.outcome=='ready_for_confirmation'
        assert strategy['extra_parameters']['recurring_contribution']==200
    else:
        assert result.outcome=='needs_clarification'
        assert conflict_event['conflicts']==[{'field_name':'asset_universe','raw_value':"['KO']",'candidate_normalized_value':['CCEP'],'reason_code':'declared_tool_input_conflict'}]
        assert result.patch['optional_parameter_status']['ambiguous_fields']==conflict_event['conflicts']
    assert calls==[{'schema':row['schema'],'retained_line':row['line']} for row in actual_audits]

with patch.object(socket.socket,'connect',forbidden),patch.object(socket.socket,'connect_ex',forbidden),patch.object(socket,'create_connection',forbidden):
    asyncio.run(main())
