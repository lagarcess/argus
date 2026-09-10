"""Execute the retained call with a controlled correct edit plan or no audit."""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
from unittest.mock import patch
repo=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(repo/'src'),str(repo)]
for key in ('ARGUS_MARKET_DATA_PROVIDER_MODE','ARGUS_ASSET_PROVIDER_MODE'):
    os.environ[key]='synthetic_unit_fixture'
os.environ['ARGUS_RESEARCH_RAIL_ENABLED']='false'
from loguru import logger
logger.remove()
from argus.agent_runtime import llm_interpreter
from argus.agent_runtime.artifact_edit_planner import ArtifactAssumptionEditPlan, EditOperation
from argus.agent_runtime.interpreter.artifact_assumption_edit import _response_from_artifact_assumption_edit_plan
from argus.agent_runtime.stages.tool_execution import execute_tool_calls_async
from argus.agent_runtime.state.models import RunState, UserState
from tests.evals import measurement_eval_harness as h
case_id='messy_spanish_post_result_fact_then_capital_edit_issue_160'
case=next(c for c in h.load_eval_cases() if c.id==case_id)
recorded=next(r for r in json.loads(Path(sys.argv[2]).read_text())['results'] if r['id']==case_id)
def no_network(*a,**kw): raise AssertionError('No network in typed edit control')
outputs=[]
async def run():
    for mode in ('no_audit','correct_capital_plan'):
        async def audit(*,response,request,**_):
            if mode=='no_audit':return response
            return _response_from_artifact_assumption_edit_plan(plan=ArtifactAssumptionEditPlan(outcome='ready_to_confirm',operations=[EditOperation(op='set',target='capital',number=2000)],confidence=.95),request=request,primary_draft=response.candidate_strategy_draft)
        state=RunState(current_user_message=case.prompt,intent='calculate',semantic_turn_act='refine_current_idea',task_relation='continue',tool_calls=recorded['typed_outcome']['tool_calls'],recent_thread_history=case.recent_thread_history)
        with patch.object(llm_interpreter,'_audited_response_ready_for_runtime',audit):
            result=await execute_tool_calls_async(state=state,tool=object(),user=UserState(user_id='control',language_preference=case.user_language),latest_task_snapshot=case.snapshot,selected_thread_metadata=case.thread_metadata)
        outputs.append({'mode':mode,'result':result.model_dump(mode='json')})
with patch.object(socket.socket,'connect',no_network),patch.object(socket,'create_connection',no_network):asyncio.run(run())
print(json.dumps(outputs,sort_keys=True))
