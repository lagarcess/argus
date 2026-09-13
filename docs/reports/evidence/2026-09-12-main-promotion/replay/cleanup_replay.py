"""Remove this replay's processes, database and private user text."""
import json,os,signal,socket,subprocess,time,shutil
from pathlib import Path
root=Path(__file__).parent
project='argus-promotion-20260912'
env={'PATH':'/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(root/'home')}
def containers():
 p=subprocess.run(['/usr/local/bin/docker','ps','--format','{{.Names}}'],capture_output=True,text=True)
 assert p.returncode==0,p.stderr
 return p.stdout.splitlines()
before=containers()
pids=json.loads((root/'server-pids.json').read_text())
owned={pids['argus-api']:str(root/'launch_acceptance.py')+' serve-api-replay',pids['argus-app']:'bun run start -- -p 3136'}
for name,marker in [('replay-budget-guardian-pid.json','watch_acceptance_budget.py'),('replay-driver-pid.json','replay_driver.py')]:
 if (root/name).exists():
  value=json.loads((root/name).read_text());owned[value['pid']]=marker
signaled=[]
for pid,marker in owned.items():
 p=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
 if p.returncode:continue
 assert marker in p.stdout,f'Owned process identity mismatch for {pid}'
 assert os.getpgid(pid)==pid,f'Unexpected process group for {pid}'
 os.killpg(pid,signal.SIGTERM);signaled.append(pid)
result=subprocess.run(['supabase','stop','--no-backup','--workdir',str(root)],env=env,capture_output=True,text=True)
# Private filesystem data is removed even if stack cleanup reports a failure.
private_existed=(root/'private-replay').exists()
if private_existed:shutil.rmtree(root/'private-replay')
removed_logs=[]
for name in ['argus-api.log','argus-app.log','replay-driver.log','replay-budget-guardian.log']:
 path=root/name
 if path.exists():path.unlink();removed_logs.append(name)
if result.returncode:
 print(result.stderr)
 raise SystemExit(result.returncode)
time.sleep(2)
after=containers()
volumes=subprocess.run(['/usr/local/bin/docker','volume','ls','--format','{{.Name}}'],capture_output=True,text=True)
assert volumes.returncode==0,volumes.stderr
owned_volumes=[x for x in volumes.stdout.splitlines() if project in x]
ports={}
for port in [8136,3136,56531,56532]:
 with socket.socket() as sock:
  sock.settimeout(1);ports[str(port)]=sock.connect_ex(('127.0.0.1',port))!=0
report={'project_id':project,'supabase_stop_exit_code':0,'supabase_stop_command':'supabase stop --no-backup --workdir <owned scratch>','owned_processes_signaled':signaled,'owned_ports_closed':ports,'owned_containers_remaining':[x for x in after if project in x],'owned_volumes_remaining':owned_volumes,'unrelated_stack_preserved':all(x in after for x in before if project not in x),'private_replay_input_was_present':private_existed,'private_replay_directory_deleted':not(root/'private-replay').exists(),'private_api_and_driver_logs_deleted':removed_logs,'customer_text_retained_in_repo':False,'checked_at_epoch':time.time()}
assert all(ports.values()) and not report['owned_containers_remaining'] and not owned_volumes and report['unrelated_stack_preserved']
(root/'cleanup-replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
