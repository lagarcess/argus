import sys, json
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'src'))
from argus.agent_runtime.stages.execute import execute_stage
from argus.agent_runtime.state.models import RunState, FinalResponsePayload
from argus.agent_runtime.graph.workflow import _patched_run_state
class Rejection:
    def run(self,payload):
        return {'success':False,'payload':None,'error_type':'account_required','error_message':None,'retryable':False,'capability_context':{'execution_status':'rejected','failure_code':'account_conversion_required'}}
state=RunState.new(current_user_message='Run backtest',recent_thread_history=[])
state.confirmation_payload={'strategy':{'asset_universe':['DOCN']}}
result=execute_stage(state=state,tool=Rejection(),max_retries=1)
converted=_patched_run_state(run_state=state,patch=result.patch)
print(json.dumps({'root':str(root),'model_fields':list(FinalResponsePayload.model_fields),'stage_patch':result.patch['final_response_payload'],'after_RunState_model_validate':converted.final_response_payload.model_dump(mode='json')},indent=2))
