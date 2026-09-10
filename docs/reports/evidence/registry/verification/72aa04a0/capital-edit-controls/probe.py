"""Controlled typed edit, not a replay of the unretained provider edit plan."""
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
from argus.agent_runtime.artifact_edit_planner import ArtifactAssumptionEditPlan, EditOperation
from argus.agent_runtime.interpreter.artifact_assumption_edit import _response_from_artifact_assumption_edit_plan
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.llm_interpreter_types import LLMStrategyDraft
from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.stages.interpret_types import InterpretationRequest
from argus.agent_runtime.state.models import UserState
from tests.evals import measurement_eval_harness as h
case_id='messy_spanish_post_result_fact_then_capital_edit_issue_160'
case=next(c for c in h.load_eval_cases() if c.id==case_id)
recorded=next(r for r in json.loads(Path(sys.argv[2]).read_text())['results'] if r['id']==case_id)
primary=LLMStrategyDraft.model_validate(recorded['typed_outcome']['tool_calls'][0]['arguments']['strategy'])
request=InterpretationRequest(current_user_message=case.prompt,user=UserState(user_id='control',language_preference=case.user_language),latest_task_snapshot=case.snapshot,recent_thread_history=case.recent_thread_history,selected_thread_metadata=case.thread_metadata)
plan=ArtifactAssumptionEditPlan(outcome='ready_to_confirm',operations=[EditOperation(op='set',target='capital',number=2000)],confidence=.95)
response=_response_from_artifact_assumption_edit_plan(plan=plan,request=request,primary_draft=primary)
interpreter=OpenRouterStructuredInterpreter(contract=build_default_capability_contract())
def no_network(*a,**kw): raise AssertionError('No network in typed edit control')
with patch.object(socket.socket,'connect',no_network),patch.object(socket,'create_connection',no_network):
    canonical=interpreter._to_runtime_interpretation(response,request=request)
    with patch.object(h,'OpenRouterStructuredInterpreter',lambda **_:lambda request:canonical),patch.object(h,'OpenRouterClarificationGenerator',lambda:lambda request:'Choose how to continue.' ):
        result=h.run_eval_case(case,run_prose_judge=False)
print(json.dumps({'repository':str(repo),'boundary':'controlled typed capital edit after unretained provider plan','primary_from_live_call':primary.model_dump(mode='json'),'planned_draft':response.candidate_strategy_draft.model_dump(mode='json'),'canonical_strategy':canonical.candidate_strategy_draft.model_dump(mode='json'),'result':result},sort_keys=True))
