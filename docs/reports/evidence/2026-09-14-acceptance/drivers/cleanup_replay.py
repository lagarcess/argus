"""Promotion cleanup adapted to this lane's owned processes, stack and private files."""
import json,os,signal,socket,subprocess,time,shutil
from pathlib import Path
S=Path('/private/tmp/argus-acceptance-20260914');E=Path(__file__).resolve().parent.parent
project='argus-acceptance-20260914'
def inventory(kind):
 args=['docker','ps','--format','{{.Names}}'] if kind=='containers' else ['docker','volume','ls','--format','{{.Name}}']
 p=subprocess.run(args,capture_output=True,text=True);assert p.returncode==0,p.stderr;return p.stdout.splitlines()
before=inventory('containers');pids=json.loads((S/'server-pids.json').read_text());owned={pids['argus-api']:'launch.py serve-api',pids['argus-app']:'bun run start -- -p 3149'}
for name,marker in [('watch-pid.json','watch_acceptance_budget.py'),('replay-driver-pid.json','replay_driver.py')]:
 if (S/name).exists():owned[json.loads((S/name).read_text())['pid']]=marker
signaled=[]
for pid,marker in owned.items():
 p=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
 if p.returncode:continue
 assert marker in p.stdout,f'Owned process identity mismatch: {pid}'
 assert os.getpgid(pid)==pid
 os.killpg(pid,signal.SIGTERM);signaled.append(pid)
result=subprocess.run(['supabase','stop','--no-backup','--workdir',str(S/'stack')],capture_output=True,text=True)
private_existed=(S/'replay-control/private-replay').exists()
# Remove every private input, response, account secret, API log and build copy.
shutil.rmtree(S)
assert result.returncode==0,'Disposable stack stop failed; private files were still removed'
time.sleep(2);after=inventory('containers');volumes=inventory('volumes')
ports={}
for port in [8149,3149,56731,56732]:
 with socket.socket() as sock:sock.settimeout(1);ports[str(port)]=sock.connect_ex(('127.0.0.1',port))!=0
report={'project_id':project,'supabase_stop_exit_code':result.returncode,'owned_processes_signaled':signaled,'owned_ports_closed':ports,'owned_containers_remaining':[x for x in after if project in x],'owned_volumes_remaining':[x for x in volumes if project in x],'unrelated_stack_preserved':all(x in after for x in before if project not in x),'private_replay_input_was_present':private_existed,'private_directory_and_logs_deleted':not S.exists(),'customer_text_retained_in_repo':False,'checked_at_epoch':time.time()}
(E/'cleanup-proof.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(ports.values()) and not report['owned_containers_remaining'] and not report['owned_volumes_remaining'] and report['unrelated_stack_preserved']
print(json.dumps(report))
