"""External native-run observer. Never changes product or native eval behavior."""
import argparse, hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import dotenv_values

p=argparse.ArgumentParser();p.add_argument('--tree',type=Path,required=True);p.add_argument('--expected-sha',required=True);p.add_argument('--preflight',action='store_true');a=p.parse_args()
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
cases=load_eval_cases();assert len({c.id for c in cases})==len(cases)
out=root/'temp/release-evidence';observer={'schema_version':1,'measured_sha':a.expected_sha,'observer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'before':before,'fixture_count':len(cases),'preflight':a.preflight,'started_at':datetime.now(timezone.utc).isoformat()}
(out/'native-configuration-observer.json').write_text(json.dumps(observer,indent=2)+'\n')
print(json.dumps({'preflight':a.preflight,'sha':a.expected_sha,'fixtures':len(cases),'configuration_matches':True,'imports_native_tree':True}),flush=True)
if a.preflight:sys.exit(0)
import pytest, time
import tests.evals.measurement_eval_harness as native_harness
native_run=native_harness.run_eval_case
def observed_run(case):
 started=time.monotonic()
 result=native_run(case)
 event={'id':case.id,'status':result['status'],'elapsed_seconds':round(time.monotonic()-started,3),'result':result}
 with (out/'native-case-results.jsonl').open('a') as f:f.write(json.dumps(event,default=str)+'\n')
 print(json.dumps({k:v for k,v in event.items() if k!='result'}),flush=True)
 return result
native_harness.run_eval_case=observed_run
old=set((root/'temp/argus_eval_scorecards').glob('*.json'))
code=pytest.main(['tests/evals/test_measurement_eval_live.py','--confcutdir=tests/evals','-q','--no-cov','-s'])
after=observe();assert before==after
observer.update(after=after,pytest_exit=int(code),finished_at=datetime.now(timezone.utc).isoformat())
(out/'native-configuration-observer.json').write_text(json.dumps(observer,indent=2)+'\n')
new=set((root/'temp/argus_eval_scorecards').glob('*.json'))-old
assert len(new)==1,new
source=new.pop();doc=json.loads(source.read_text());assert doc['provenance']['candidate_sha']==a.expected_sha
if doc['schema_version']==2:
 # Preserve the native schema-2 artifact; bind contemporaneously observed config in a separate copy.
 doc['schema_version']=3;doc['provenance']['release_configuration']=before
 doc['configuration_observer']={'sha256':observer['observer_sha256'],'native_source':source.name,'before_after_match':True}
else:assert doc['provenance']['release_configuration']==before
(out/'observed-native-scorecard.json').write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
print(json.dumps({'totals':doc['totals'],'provider_usage':doc['provider_usage'],'pytest_exit':int(code)}),flush=True)
sys.exit(int(code))
