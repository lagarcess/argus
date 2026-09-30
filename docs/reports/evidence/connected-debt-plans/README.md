# Connected debt-payment plans local demonstration

The retained scene uses real local Supabase Auth, Postgres and the Argus API with
synthetic data. Native integration and independent review are still in progress.
This checkpoint proves the API journey; it is not physical-phone delivery.

Delivery checkout: `/Users/garces/.codex/worktrees/connected-debt-plans/private-alpha-next`.
Branch: `codex/connected-debt-plans`. Integration base: `7c29b2a9b3f4680f6804a2abc8378df45b05540c`.

## Retained environment

API 59200, Supabase 59201, Postgres 59202, synthetic CAPTCHA 59205,
response-loss proxy 59212 and native simulator mirror 59213 are lane-owned.
Simulator **Argus Foundation Compact**, `1A90F684-345F-465C-AA50-6A5298F34156`,
uses the separate debt app bundle `local.argus.debt-demo`. Its original app and
all previous demos remain preserved. Phone-testing ports 58700–58749 are untouched.

Private synthetic credentials and exact-command journals remain in ignored
`ios/.build/accounts-local-59200/`. Do not publish those files. Restart reuses the
existing users, database and records.

## Restart

Skip a service that is already running. Run each service in its own terminal.
Never configure, seed, reset or delete volumes for this retained scene.

```sh
cd /Users/garces/.codex/worktrees/connected-debt-plans/private-alpha-next
python3 ios/scripts/auth/local_stack.py start --accounts --port-base 59200
python3 ios/scripts/auth/local_stack.py api --accounts --port-base 59200 \
  --accounts-enabled on \
  --python /Users/garces/.codex/worktrees/5a42/private-alpha-next/.venv/bin/python
```

```sh
cd /Users/garces/.codex/worktrees/connected-debt-plans/private-alpha-next
python3 ios/scripts/auth/bridge.py --accounts --port-base 59200
```

Boot only this simulator if it is shut down. Launch the debt app after its native
build has been installed.

```sh
xcrun simctl bootstatus 1A90F684-345F-465C-AA50-6A5298F34156 -b
xcrun simctl launch 1A90F684-345F-465C-AA50-6A5298F34156 local.argus.debt-demo \
  -AppleLanguages '(en)' -AppleLocale en_US -appearancePreference dark
```

If the native mirror is absent, start it separately. Cleanup targets only this
simulator's mirror.

```sh
cd /Users/garces/.codex/worktrees/connected-debt-plans/private-alpha-next
DEBT_SIM=1A90F684-345F-465C-AA50-6A5298F34156
cleanup_debt_mirror() {
  npx --yes serve-sim@0.1.47 --kill "$DEBT_SIM" >/dev/null 2>&1 || true
}
trap cleanup_debt_mirror EXIT INT TERM HUP
cleanup_debt_mirror
npx --yes serve-sim@0.1.47 --port 59213 --host 127.0.0.1 \
  --codec mjpeg --fit "$DEBT_SIM"
```

[Open the native simulator](http://localhost:59213). Confirm **Argus Foundation
Compact** is selected. The mirror displays and controls the native app.

## API proof and recovery

[debt-api-proof.json](debt-api-proof.json) records independently expected balances,
costs, remaining commitments and savings backing. The fixture suffix is
`c801d065`. Its primary retained loan has DOP 500 recorded principal, a DOP 500
monthly plan, DOP 85 actual interest/fees, and three linked canonical payments.
The funding account has DOP 1,560; DOP 1,500 remains assigned to the existing
savings goal, leaving DOP 60 unassigned. USD and unknown debt stay separate.

The optional model uses explicit 12% nominal annual interest, zero recurring
fees, monthly periods and no new borrowing. Its two projected payments and DOP
5.05 projected interest do not alter recorded balances or spending. A later
statement check changes recorded principal and preserves any unexplained
difference; it does not invent interest or fees.

```sh
cd /Users/garces/.codex/worktrees/connected-debt-plans/private-alpha-next
python3 ios/scripts/debts-journey.py readback
```

Readback verifies this retained fixture. After deliberate human edits, use
`readback --observe`; that writes a separately labelled observation and does
not overwrite the accepted proof. To recover an interrupted initial run,
`run` resends the pending command's exact bytes and key before further writes.
Do not delete the private journal to replay the demo.

The already-proven response-loss case used the bounded local proxy below. It
lost a successful debt-plan creation response, then recovered the same accepted
receipt with no duplicate plan. Native write recovery remains to be demonstrated.

```sh
python3 scripts/qa/financial_response_fault.py \
  --listen-port 59212 --upstream-port 59200
python3 ios/scripts/debts-journey.py run --response-loss
```

## Verified at this checkpoint

Actual loan splits, linked existing payments, multiple partial payments,
corrections, extra payments and overpayment credit update Accounts, Plan and Home
once. Real partial/full returns preserve original history and costs in their
original period, reverse costs in the return period and reopen recorded debt.
Cards do not count purchases again. Unknown balances remain unknown. Currencies
remain isolated. The existing budget and savings pool reflect actual costs and
funding shortfalls. Archive/restore, stale writes, owner isolation, missed
occurrences, reconciliation and exact retries passed against real Postgres.

Remaining acceptance is the connected native flow, English/Spanish, Search/back,
relaunch, native interrupted writes, durable visuals/recording, CI and fresh
independent review. There is no physical iPhone installation, hosted deployment,
real lender execution or automatic interest accrual in this assignment.
