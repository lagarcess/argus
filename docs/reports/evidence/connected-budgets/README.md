# Connected spending budget demonstration

The [execution manifest](../../../specs/argus-execution-board.md#connected-personal-spending-budgets-lane)
owns scope, decisions and delivery status. This guide preserves only the isolated
local environment. The founder approved the original financial policy and resumed implementation.
Budget implementation and connected acceptance are in progress. The installed app currently inherits the landed recording, Plan and Search
features. This is not a completed budget demonstration or physical-phone proof.

## Preserve the environment

Use `/Users/garces/.codex/worktrees/connected-budgets/private-alpha-next` on
`codex/connected-budgets`. The dedicated simulator is `Argus Connected Budgets`,
iPhone 17e with iOS 27, `CC81C737-2F0A-48EA-961C-D9ECFFACA219`.
The installed bundle identifier is `local.argus.foundation`.

The stack uses API 59000, Supabase 59001, Postgres 59002 and synthetic CAPTCHA
bridge 59005. The clickable mirror uses loopback port 59013. Optional response-loss
acceptance uses 59012. No service is publicly exposed. Existing demonstrations
and the physical-phone environment on ports 58700-58749 remain separate.

The ignored `ios/.build/accounts-local-59000/client.json` holds the two local
synthetic users. Do not publish that file, write journals or authentication logs.
Do not run `configure`, `seed`, a database reset or volume deletion on restart.

## Restart without losing records

Skip any service already running. Start each long-running service in its own
terminal and keep that terminal open.

```sh
cd /Users/garces/.codex/worktrees/connected-budgets/private-alpha-next
python3 ios/scripts/auth/local_stack.py start --accounts --port-base 59000
python3 ios/scripts/auth/local_stack.py api --accounts --port-base 59000 \
  --accounts-enabled on \
  --python /Users/garces/.codex/worktrees/5a42/private-alpha-next/.venv/bin/python
```

```sh
cd /Users/garces/.codex/worktrees/connected-budgets/private-alpha-next
python3 ios/scripts/auth/bridge.py --accounts --port-base 59000
```

Launch only this lane's simulator. Boot it only if it is shut down.

```sh
xcrun simctl boot CC81C737-2F0A-48EA-961C-D9ECFFACA219
xcrun simctl launch CC81C737-2F0A-48EA-961C-D9ECFFACA219 local.argus.foundation
```

If the mirror is not running, start it in a separate terminal. Its cleanup targets
only the budget simulator.

```sh
cd /Users/garces/.codex/worktrees/connected-budgets/private-alpha-next
BUDGET_SIM=CC81C737-2F0A-48EA-961C-D9ECFFACA219
cleanup_budget_mirror() {
  npx --yes serve-sim@0.1.47 --kill "$BUDGET_SIM" >/dev/null 2>&1 || true
}
trap cleanup_budget_mirror EXIT INT TERM HUP
cleanup_budget_mirror
npx --yes serve-sim@0.1.47 --port 59013 --host 127.0.0.1 \
  --codec mjpeg --fit "$BUDGET_SIM"
```

[Open the local simulator mirror](http://localhost:59013). Its selected device must
be **Argus Connected Budgets**. The captain verified a live native frame; a loaded
HTML page alone does not prove streaming or financial behavior.

## Verification status

[The pre-implementation baseline](baseline.json) records 203 inherited financial
tests with zero skips against this lane's disposable Postgres. Registered native
sign-in, relaunch, sign-out and signed-out relaunch also passed against real local
Auth/API/Postgres. Raw logs and `.xcresult` diagnostics remain ignored.

[The fixture proof](fixture-api-proof.json) independently verifies five accounts
and eight canonical activities after repeated setup. It includes bank/card
purchases, a transfer, a card payment, another currency and an unknown balance.
Fifteen real API readbacks cover balances, entry identity and owner isolation.
The inherited Home reopening test also passes. Its [retained Home screenshot](pre-implementation-home.png)
shows DOP 963 in known balances, one unknown balance, DOP 140 spending and
USD 50 separately. These are preparation evidence, not budget progress.

`python3 ios/scripts/budgets-acceptance.py setup` resumes the exact saved fixture
writes without regenerating completed records. `readback` verifies only this
initial baseline, before later interactive demo changes. Neither command creates
a budget or defines which records a budget includes.

Budget create/edit/progress, contributing-entry return, budget Search, interrupted
writes, localization and the connected recording remain unverified. No merge-ready
claim, deployment or physical-device installation has occurred.
