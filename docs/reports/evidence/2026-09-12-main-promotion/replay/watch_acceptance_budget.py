"""Stop only this disposable API when a paid acceptance phase reaches its guard."""
import argparse
import json
import os
import signal
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--phase', choices=['browser', 'replay'], required=True)
parser.add_argument('--api-pid', type=int, required=True)
args = parser.parse_args()
root = Path(__file__).parent
limit = 3.0 if args.phase == 'browser' else 4.0
ledger = root / f'{args.phase}-costs.jsonl'
status_path = root / f'{args.phase}-budget-status.json'
while True:
    events = []
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # A concurrent append may be incomplete until the next poll.
    costs = [event for event in events if event.get('kind') == 'cost']
    tracked = sum(float(event['cost_usd']) for event in costs if event.get('cost_usd') is not None)
    unknown = sum(event.get('cost_usd') is None and event.get('outcome') != 'skipped' for event in costs)
    reserve = 0.10 + 0.02 * unknown
    report = {'phase': args.phase, 'limit_usd': limit, 'tracked_cost_usd': tracked,
              'unpriced_non_skipped_receipts': unknown, 'guard_reserve_usd': reserve,
              'reserve_is_not_actual_spend': True, 'api_pid': args.api_pid,
              'state': 'watching', 'checked_at_epoch': time.time()}
    try:
        os.kill(args.api_pid, 0)
    except ProcessLookupError:
        report['state'] = 'api_stopped'
    if tracked + reserve >= limit:
        report['state'] = 'spend_stop'
        (root / f'{args.phase}-stop.json').write_text(json.dumps(report, indent=2) + '\n')
        try:
            os.killpg(args.api_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    temporary = status_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, indent=2) + '\n')
    temporary.replace(status_path)
    if report['state'] != 'watching':
        break
    if (root / f'{args.phase}-phase-complete.json').exists():
        report['state'] = 'phase_complete'
        status_path.write_text(json.dumps(report, indent=2) + '\n')
        break
    time.sleep(1)
