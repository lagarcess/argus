#!/usr/bin/env python3
"""Dedicated-emulator acceptance runner. Clears ONLY this app's data except restore.
Credentials are read from a private fixture file and redacted from test output.
Run from repository root; never select an emulator another owner is using.
"""
from pathlib import Path
import subprocess,json,sys,os
root=Path(os.environ['ARGUS_ANDROID_EVIDENCE_DIR']); root.mkdir(parents=True, exist_ok=True)
adb=str(Path(os.environ['ANDROID_HOME'])/'platform-tools/adb')
serial=os.environ.get('ARGUS_ANDROID_TEST_DEVICE','emulator-5584')
if not serial.startswith('emulator-'): raise SystemExit('This fixture runner requires a dedicated emulator.')
device=[adb,'-s',serial]
users=json.loads(Path(os.environ['ARGUS_ANDROID_IDENTITIES_JSON']).read_text());mode=sys.argv[1]
if len(users)!=2 or any(not u['email'].endswith('@example.test') for u in users):
 raise SystemExit('Use two generated disposable example.test identities.')
if mode=='install':
 for apk in ['mobile/android/app/build/outputs/apk/debug/app-debug.apk','mobile/android/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk']:
  subprocess.run(device+['install','-r',apk],check=True,stdout=subprocess.DEVNULL)
 print('Installed local Accounts app and acceptance tests.')
else:
 classes={'ui':'FinancialAccountsUiTest','core':'FinancialAccountsDeviceTest','save':'FinancialAccountsDeviceTest#serverAndApplicationRestartCheckpoint','restore':'FinancialAccountsDeviceTest#serverAndApplicationRestartCheckpoint'}
 index=int(sys.argv[2]) if len(sys.argv)>2 else 0
 if mode!='restore':subprocess.run(device+['shell','pm','clear','ai.argus.foundation.sample'],check=True,stdout=subprocess.DEVNULL)
 else:subprocess.run(device+['shell','am','force-stop','ai.argus.foundation.sample'],check=True)
 args=['shell','am','instrument','-w','-e','class',f'ai.argus.foundation.{classes[mode]}']
 values={'email':users[index]['email'],'password':users[index]['password'],'secondEmail':users[1-index]['email'],'secondPassword':users[1-index]['password'],'accountsTheme':'LIGHT' if index==0 else 'DARK'}
 if mode in ('save','restore'):values['accountsCheckpoint']=mode
 for k,v in values.items():args+=['-e',k,v]
 args+=['ai.argus.foundation.sample.test/androidx.test.runner.AndroidJUnitRunner']
 out=subprocess.run(device+args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True).stdout
 for u in users:
  for k in ('email','password'):out=out.replace(u[k],f'<synthetic-{k}>')
 (root/f'device-{mode}-{index}.log').write_text(out)
 print(out)
 if 'OK (' not in out or 'FAILURES!!!' in out:sys.exit(1)
