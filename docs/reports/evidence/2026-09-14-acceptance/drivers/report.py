"""Build the smoke report from human verdicts and durable evidence links."""
import json,hashlib
from pathlib import Path
from meter import meter
P=Path(__file__).resolve().parent.parent
verdicts=json.loads((P/'verdicts.json').read_text());records=[json.loads(p.read_text()) for p in sorted((P/'turns').glob('*.json'))]
lines=['# Integration acceptance dry run','', '**Goalpost not met: 30 of 46 smoke answers pass; 16 fail.** All smoke phases completed under the $9 cap. See [grouped causes and smallest observed reproductions](findings.md). No fixes were made.','', 'Audited product SHA: `039189128ea6ffcf59be73f3564fd936f191f662`. Drivers and evidence change only documentation. No product fix, deployment, or review requested.','',
'Goalpost: “A money question in a shape nobody wrote down lands on a primitive, gets computed or honestly bounded, and never returns a refusal that names a capability the user did not ask about.”','',
'Currency choices: answer in the reader’s home currency, match currency to the goal, cite current figures, never direct, and compute only what cited figures support. History-not-forecast applies to non-scenario answers; cited-input scenarios remain supported. Q10 additionally requires a computed, shown historical drawdown.','',
'English registered profiles: US/USD. Spanish registered profiles: DO/DOP. Guests have no home-country setting. Each initial smoke question gets an isolated conversation, and its follow-up uses that conversation. Requests are sent through the real web composer; screenshots are 390 × 844 CSS pixels. Stored metadata and route receipts are read from local Supabase.','',
'Environment: production web build and real auth/Postgres/live providers. See [environment proof](environment-proof.json). As in the September 12 local promotion, the exceptions are localhost endpoints/CAPTCHA, in-process backtests, no PostHog, and no outgoing application email. This is behavioral acceptance evidence, not deployed-service parity proof.','',
'## Results','', '| Answer | Verdict | Reason | Baseline comparison | Evidence |','|---|---|---|---|---|']
for r in records:
 label=r['label'];v=verdicts.get(label,{});result='PASS' if v.get('pass') is True else 'FAIL' if v.get('pass') is False else 'NOT JUDGED'
 shot=r.get('screenshot',{}).get('file');assert shot and (P/shot).exists(),label
 links=f'[phone]({shot}), [stored turn](turns/{label}.json), [text](answers/{label}.md)'
 lines.append('| '+' | '.join([label,result,v.get('reason',''),v.get('baseline','Follow-up or guest repeat.'),links]).replace('\n',' ')+' |')
lines+=['','## Spend','', 'Provider-reported values and unpriced estimates are separate. Estimates are not invoices. Route attempts with missing usage reserve $0.02; research usage is priced with the repository table. A missing research invoice reserves table-priced assumed token/tool usage. A further $0.65 is held before admitting another turn. No claim is made that a provider invoice cannot later revise this estimate.','', '| Phase | Reported USD | Unpriced estimate USD | Metered USD |','|---|---:|---:|---:|']
for phase,s in meter()['phases'].items():lines.append(f"| {phase} | {s['reported_usd']:.6f} | {s['unpriced_estimate_usd']:.6f} | {s['metered_usd']:.6f} |")
lines+=['','See [meter](meter.json), [phase admissions](phase-admission.json), and [cost events](cost-events.jsonl).','']
lines += ['## Scope and evidence limits','', 'Registered initial: 15 pass / 5 fail. Follow-ups: 9 pass / 11 fail. Guest repeats: 6 pass / 0 fail. All 46 have 390 × 844 screenshots and stored route/failure metadata. Q9 tests stop at the normal execution confirmation, as in the committed smoke evidence; no new completed backtest is claimed. See [baseline comparison](baseline-comparison.json), [driver notes](README.md), and [artifact privacy check](artifact-privacy-check.json).','']
replay_path=P/'replay-results.json'
if replay_path.exists():
 replay=json.loads(replay_path.read_text())
 lines += ['## Private August 12 replay','', f"{replay['passed']} passed; {replay['failed']} failed; {replay['allowance']} allowance-limited; {replay['not_run']} not run, from 15 conversations and 38 ordered turns. Same product SHA and fresh guest identity per conversation.",'', 'Each turn was assessed privately against both the goalpost and the refusal rule. Automatic approval review rejected printing private transcript text; the replacement assessor returns only fixed verdict codes. These are model-assessed semantic verdicts, not an independent human review of every reply. The assessor uses the release structured model, and its provider receipts are included in replay spend. Customer text, responses and screenshots are excluded from committed replay evidence. Privacy exception: one initial private turn appeared in tool output before the switch; local cleanup cannot erase that tool history.','', '| Case | Turn | Verdict | Reason | Refusal violation |','|---|---|---|---|---|']
 for r in replay['turns']:
  lines.append(f"| {r['case_number']:02d} | {r['turn_number']:02d} | {r['outcome'].upper()} | {r['reason']} | {r.get('refusal_violation', False)} |")
 lines += ['', 'Stored routes, costs and failure codes are in [replay-results.json](replay-results.json). See [budget-stop accounting](replay-budget-stop.json): the guard first stopped at $3.90; removing a duplicate invoice-diagnostic reserve and finishing the delivered assessment gives $3.28. The remaining budget cannot cover another observed large research call, so 24 turns were not run. The September 12 baseline passed 38/38 on the refusal rule alone; this run adds the full goalpost, so the two overall acceptance counts do not measure identical criteria.','']
 failures={}
 for r in replay['turns']:
  if r['outcome']=='fail':failures.setdefault(r.get('reason_code',r.get('refusal_code')),[]).append(r)
 if failures:
  lines += ['### Replay failures by cause','', 'The smallest retained reproduction is the numbered conversation prefix ending at the first failing turn. No extra paid reduction was attempted, and no customer text is quoted. The private prefixes were deleted after assessment.','']
  for cause,rows in failures.items():
   first=rows[0];lines += [f"- `{cause}`: {len(rows)} turns. First observed prefix: case {first['case_number']:02d}, through turn {first['turn_number']:02d}. {first['reason']}"]
 lines += ['', 'Privacy and cleanup: [cleanup-proof.json](cleanup-proof.json). Private input, response and log files and the disposable database are removed at completion.','']
if (P/'lineage-proof.json').exists():lines += ['## Lineage','', '[Lineage proof](lineage-proof.json) records the original and final observed integration heads. The archived tested product never changed during the run. Later integration changes are outside this evidence.','']
(P/'report.md').write_text('\n'.join(lines))
hashes={str(p.relative_to(P)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (P/'screenshots').glob('*.png')};(P/'screenshot-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
print(json.dumps({'recorded':len(records),'passed':sum(v.get('pass') is True for v in verdicts.values()),'failed':sum(v.get('pass') is False for v in verdicts.values())}))
