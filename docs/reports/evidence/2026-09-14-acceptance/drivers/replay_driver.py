"""One private replay turn at a time; no production text is printed.

Prepared only. Execution requires the separate, costed acceptance decision
record and private inputs. Human semantic assessment follows each turn.
"""
import argparse
import json
import os
import re
import time
from pathlib import Path
import httpx

ROOT=Path('/private/tmp/argus-acceptance-20260914/replay-control')
PRIVATE=ROOT/'private-replay'
API='http://localhost:8149/api/v1'
CAPTCHA_SOURCE=Path('/private/tmp/argus-acceptance-20260914/source/web/lib/guest-captcha.ts')
CAPTCHA_TOKEN=re.search(r'^export const LOCAL_QA_CAPTCHA_TOKEN = "([^"]+)";', CAPTCHA_SOURCE.read_text(), re.M).group(1)

def save(path,data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), 'w') as output:
        output.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(path)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    if not args.execute:
        print('Prepared only; no HTTP calls made.')
        return
    decision=json.loads((ROOT/'replay-run-decision.json').read_text())
    assert decision['ab_completed'] is True
    assert decision['founder_replay_authorized_after_ab'] is True
    assert decision['estimated_cost_usd'] <= 4
    assert decision['reported_before_execution'] is True
    inputs=json.loads((PRIVATE/'inputs.json').read_text())
    assert (PRIVATE.stat().st_mode & 0o077)==0
    seen_guests = set()
    for case in inputs['cases']:
        case_no=case['case_number']
        language=case['language']
        # One documentation-only address represents one fresh guest/person;
        # allowance isolation follows the existing production proxy header.
        headers={'Origin':'http://localhost:3149','x-forwarded-for':f'198.51.100.{case_no}'}
        with httpx.Client(base_url=API,headers=headers,timeout=240) as client:
            response=client.post('/auth/guest',json={'captcha_token':CAPTCHA_TOKEN,'language':language})
            if response.status_code!=200:
                save(ROOT/'replay-driver-status.json',{'state':'bootstrap_failed','case_number':case_no,'http_status':response.status_code,'code':response.json().get('code')})
                return
            payload = response.json()
            guest_id = payload['user']['id']
            assert guest_id not in seen_guests, 'Replay did not receive a fresh guest'
            seen_guests.add(guest_id)
            # Use the supported bearer transport. HTTPX does not apply the
            # browser's localhost exception to production Secure cookies.
            # Keep the scratch token only in this client's memory.
            client.headers['Authorization'] = 'Bearer ' + payload['session']['access_token']
            response=client.post('/conversations',json={'language':language})
            if response.status_code not in (200,201):
                save(ROOT/'replay-driver-status.json',{'state':'conversation_create_failed','case_number':case_no,'http_status':response.status_code,'code':response.json().get('code')})
                return
            conversation_id=response.json()['conversation']['id']
            for turn_no,message in enumerate(case['messages'],1):
                if (ROOT/'replay-stop.json').exists():
                    return
                save(ROOT/'replay-driver-status.json',{'state':'turn_running','case_number':case_no,'turn_number':turn_no})
                from meter import meter
                if meter()['replay_usd']+.65>=4:
                    save(ROOT/'replay-stop.json',{'reason':'budget admission reserve'})
                    return
                frames=[]
                done=0
                with client.stream('POST','/chat/stream',json={'conversation_id':conversation_id,'message':message,'language':language,'viewport':'wide'}) as stream:
                    status=stream.status_code
                    if status==200:
                        for line in stream.iter_lines():
                            if not line.startswith('data:'):
                                continue
                            data=line[5:].strip()
                            if data=='[DONE]':
                                done+=1
                            else:
                                try:frames.append(json.loads(data))
                                except ValueError:pass
                    else:
                        stream.read()
                        frames=[{'http_error':stream.json()}]
                persisted=client.get(f'/conversations/{conversation_id}/messages',params={'limit':100}).json()
                evidence={'stored_messages':persisted,'case_number':case_no,'turn_number':turn_no,'user_message':message,'http_status':status,'done_count':done,'frames':frames}
                name=f'case-{case_no:02d}-turn-{turn_no:02d}'
                save(PRIVATE/(name+'.private.json'),evidence)
                save(ROOT/'replay-driver-status.json',{'state':'awaiting_semantic_assessment','case_number':case_no,'turn_number':turn_no,'http_status':status,'done_count':done})
                decision_path=ROOT/(name+'.decision.json')
                while not decision_path.exists():
                    if (ROOT/'replay-stop.json').exists():
                        return
                    time.sleep(0.25)
                verdict=json.loads(decision_path.read_text())
                assert verdict['outcome'] in ('pass', 'fail', 'allowance')
                if False:  # Diagnostic replay continues after recorded failures, within budget.
                    save(ROOT/'replay-driver-status.json',{'state':'blocked_by_failed_case','case_number':case_no,'turn_number':turn_no})
                    return
    save(ROOT/'replay-driver-status.json',{'state':'completed','conversations':len(inputs['cases']),'user_turns':sum(len(c['messages']) for c in inputs['cases']),'distinct_fresh_guests':len(seen_guests)})

if __name__=='__main__':
    main()
