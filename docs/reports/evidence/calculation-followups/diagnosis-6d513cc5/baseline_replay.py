import json
from pathlib import Path
from argus.agent_runtime.llm_interpreter_types import LLMInterpretationResponse
from argus.agent_runtime.answer_calculation import render_answer_text
from argus.domain.tool_contracts import ToolResultCard
from pydantic import ValidationError
print('source:', __import__('argus.agent_runtime.answer_calculation', fromlist=['']).__file__)
for field in ('candidate_strategy_draft','response_profile_overrides'):
    try:
        LLMInterpretationResponse.model_validate({'intent':'unsupported_or_out_of_scope','task_relation':'new_task','user_goal_summary':'Unsupported options',field:None})
        print('null object',field,'accepted')
    except ValidationError as e:
        print('null object',field,'rejected', e.errors()[0]['type'])
data=json.loads(Path('docs/reports/evidence/calculation-followups/measurement-faeff8e4/live-measurement.json').read_text())
for case in ('calculation_followups_q3_periods_and_profile_currency_en','calculation_followups_q3_periods_and_profile_currency_es_419'):
    result=next(r for r in data['results'] if r['id']==case)
    card=ToolResultCard.model_validate(result['typed_outcome']['calculations'][0])
    prose=result['prose_judge']['judged_assistant_text']['text']
    print(case, render_answer_text(prose,{'calculation_1':card}))
import asyncio
from argus.agent_runtime import research_answer as ra
from argus.agent_runtime.stages.interpret_types import StructuredInterpretation
from argus.agent_runtime.state.models import RunState, UserState
from argus.agent_runtime.research_query import ResearchQueryExtraction
from argus.agent_runtime.interpreter.research_routing import unkinded_question_research_query
read=StructuredInterpretation(intent='conversation_followup', task_relation='new_task', user_goal_summary='Earlier answer',semantic_turn_act='educational_question')
print('missing-query educational fallback:',unkinded_question_research_query(read).question_kind)
def no_provider(*args, **kwargs):
    raise AssertionError('This is a free boundary replay; no provider dispatch is permitted')
ra.grounded._client = no_provider
ra._resolved_subjects=lambda query:[]
result=asyncio.run(ra._dispatch(ResearchQueryExtraction(question_kind='live_quote',asset_class_hint='currency_pair'),interpretation=read,state=RunState.new(current_user_message='Current selling rate',recent_thread_history=[]),user=UserState(user_id='free-replay'),discovery_request=None,decision=None))
print('uncovered currency fact:',result.stage_patch['research'].get('degraded'), 'sources:',len(result.stage_patch['research'].get('sources',[])))
