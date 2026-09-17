"""External native-run observer. Never changes product or native eval behavior."""
import argparse, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import dotenv_values

p=argparse.ArgumentParser();p.add_argument('--tree',type=Path,required=True);p.add_argument('--expected-sha',required=True);p.add_argument('--preflight',action='store_true');p.add_argument('--case-id',required=True);p.add_argument('--round',type=int,default=0);p.add_argument('--side',choices=['baseline','candidate'],required=True);a=p.parse_args()
root=a.tree.resolve();os.chdir(root)
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==a.expected_sha
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
for k in list(os.environ):
 if k.startswith(('ARGUS_','ALPACA_','OPENROUTER_','PERPLEXITY_','SUPABASE_')) or k in ('APP_ENV','DATABASE_URL'):os.environ.pop(k)
envfile=root/'temp/release-evidence/live.env'
os.environ.update({k:v for k,v in dotenv_values(envfile).items() if v is not None})
os.environ['ARGUS_EVAL_ENV_FILE']=str(envfile)
sys.path[:0]=[str(root),str(root/'src')]
import tests.evals.measurement_eval_scorecard as native_scorecard
if hasattr(native_scorecard, 'assert_eval_env_file_untracked'):
 native_scorecard.assert_eval_env_file_untracked(envfile)
else:
 assert envfile.is_file() and not envfile.is_symlink()
 assert subprocess.run(['git','check-ignore','-q',str(envfile)],cwd=root).returncode==0
 assert not subprocess.check_output(['git','ls-files','--',str(envfile)],cwd=root,text=True).strip()
from argus.llm.openrouter import _env_model_value
import argus.llm.memory_embedding as embedding
from tests.evals.measurement_eval_harness import load_eval_cases
profile=json.loads((root/'.github/private-alpha-release-profile.json').read_text())['services']['api']['env']
keys=[k for k,v in profile.items() if k.endswith('_MODEL') or v in ('true','false')]
def observe():
 result={}
 for k in keys:
  if k=='ARGUS_MEMORY_EMBEDDING_MODEL':
   if hasattr(embedding,'resolve_memory_embedding_model'):result[k]=embedding.resolve_memory_embedding_model()
   else:
    embedder=embedding.perplexity_embedder_from_env()
    assert embedder is not None
    result[k]=embedder._model
  elif k.endswith('_MODEL'):result[k]=_env_model_value(k)
  else:result[k]=os.getenv(k).strip().lower() if os.getenv(k) is not None else None
 for name,module in list(sys.modules.items()):
  if name=='argus' or name.startswith('argus.') or name=='tests' or name.startswith('tests.'):
   if getattr(module,'__file__',None):assert Path(module.__file__).resolve().is_relative_to(root),(name,module.__file__)
 return result
before=observe();assert before=={k:profile[k] for k in keys}

cases={case.id:case for case in load_eval_cases()}
assert a.case_id in cases,a.case_id
out=root/'temp/release-evidence/targeted';out.mkdir(parents=True,exist_ok=True)
path=out/f'{a.case_id}-{a.side}-{a.round:02}.json'
assert a.preflight or not path.exists(), 'Never repeat a recorded attempt'
if a.preflight:
 print(json.dumps({'case_id':a.case_id,'side':a.side,'sha':a.expected_sha,'configuration_matches':True,'native_case_exists':True}));sys.exit(0)
from dataclasses import asdict
import time
from tests.evals.measurement_eval_harness import run_eval_case
provenance=asdict(native_scorecard.build_scorecard_provenance(evaluation_mode='live'))
provenance['release_configuration']=before
started=time.monotonic();result=run_eval_case(cases[a.case_id]);after=observe();assert after==before
payload={'case_id':a.case_id,'side':a.side,'round':a.round,'provenance':provenance,'result':result,'elapsed_seconds':time.monotonic()-started,'observer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'configuration_before_after_match':True}
path.write_text(json.dumps(payload,indent=2,default=str)+'\n')
print(json.dumps({'case_id':a.case_id,'side':a.side,'round':a.round,'status':result['status']}))
