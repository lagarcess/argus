"""Free instrumentation identity/control check; writes no live scorecard."""
import asyncio,json,runpy,socket,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from argus.llm import openrouter
from tests.evals import measurement_eval_harness as h, measurement_eval_scorecard as s
root=Path.cwd()
class Response:
 status_code=200
 def json(self): return {'choices':[{'message':{'content':'captured response'}}]}
response=Response(); observed=[]
request={'payload':{'model':'fixture','response_format':{'json_schema':{'name':'ArgusProseJudgeResponse'}},'messages':[{'role':'user','content':'authored fixture'}]},'headers':{'Authorization':'secret-should-not-appear'},'retry_attempt':('fixture',1)}
def original_sync(**kwargs):
 assert kwargs==request; observed.append('sync');return response
async def original_async(**kwargs):
 assert kwargs==request; observed.append('async');return response
research={'usage':{'cost_usd':.2,'cache_status':'miss'}}
patch_value={'research':research}
def original_patch(*args,**kwargs): return patch_value
result={'id':'instrumentation_control','status':'passed','failed_checks':[]}
def run_case(case):
 assert openrouter._post_openrouter_json_schema_sync(**request) is response
 assert asyncio.run(openrouter._post_openrouter_json_schema(**request)) is response
 assert h._final_patch() is patch_value
 return result
checks=[]
def forbidden(*a,**kw): raise AssertionError('network forbidden')
with tempfile.TemporaryDirectory(prefix='registry-wrapper-control-',dir='/private/tmp') as tmp:
 tmp=Path(tmp);env=tmp/'fixture.env';env.write_text('')
 output=tmp/'not-live.json'
 argv=['retained-case-probe.py','--repository',str(root),'--environment',str(env),'--case','instrumentation_control','--label','mocked-instrumentation-control','--output',str(output)]
 with patch.dict('os.environ',{'ARGUS_RUN_LIVE_EVALS':'1'}),patch.object(sys,'argv',argv),patch.object(socket.socket,'connect',forbidden),patch.object(socket,'create_connection',forbidden),patch.object(openrouter,'_post_openrouter_json_schema',original_async),patch.object(openrouter,'_post_openrouter_json_schema_sync',original_sync),patch.object(h,'_final_patch',original_patch),patch.object(h,'load_eval_cases',lambda:[SimpleNamespace(id='instrumentation_control',raw={'id':'instrumentation_control'})]),patch.object(h,'run_eval_case',run_case),patch.object(s,'build_scorecard_provenance',lambda **_:SimpleNamespace(candidate_sha='authored-control-not-a-sha')),patch.object(s,'assert_provenance_matches_current_run',lambda _:checks.append('final_provenance_assertion_called')),patch.object(s,'validated_provenance_payload',lambda _:{'evaluation_mode':'mocked-instrumentation-control'}),patch.object(s,'_provider_usage',lambda _:{'mocked':True}):
  runpy.run_path(str(root/'docs/reports/evidence/registry/verification/retained-case-probe.py'),run_name='__main__')
  assert openrouter._post_openrouter_json_schema_sync is original_sync
  assert openrouter._post_openrouter_json_schema is original_async
  assert h._final_patch is original_patch
 data=json.loads(output.read_text());responses=output.with_suffix('.responses.jsonl').read_text()
 assert data['results']==[result]
 assert data['observed_final_research_sidecar']==research
 assert 'secret-should-not-appear' not in responses
 assert all(r['judge_request_payload']==request['payload'] for r in map(json.loads,responses.splitlines()))
 assert observed==['sync','async'] and checks==['final_provenance_assertion_called']
print(json.dumps({'evidence_type':'free mocked instrumentation control','network_calls':0,'original_arguments_and_response_identity':True,'original_patch_identity_and_grade':True,'judge_payload_retained':True,'headers_excluded':True,'final_provenance_check_and_function_restoration':True,'mocked_scorecard_deleted':True}))
