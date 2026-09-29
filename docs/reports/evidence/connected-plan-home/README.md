# Connected Plan and Home: local iPhone demonstration

This lane connects expected income, bills, recurrence and fulfillment to the
existing recording service. The [execution manifest](../../../specs/argus-execution-board.md#connected-plan-and-home-lane)
owns scope, status and the remaining MVEE work. Physical-iPhone installation and
internet deployment are not verified by this local demonstration.

## Retained environment

The dedicated simulator is **Argus Connected Plan**, iPhone 17e / iOS 27,
`4E22655F-72DC-468F-AEBB-97FBDC58B514`, bundle `local.argus.foundation`.
It uses real local Argus Auth/API/Postgres with synthetic registered identities:
API58600, Supabase58601, Postgres58602 and CAPTCHA58605. No paid providers are
configured. The older584xx financial loop and585xx personal-money demos remain
separate.

The ignored `ios/.build/accounts-local-58600/client.json` holds the synthetic
credentials. Never publish it or raw authentication logs. The installed app keeps
its session in the simulator Keychain.

## Click through

1. Open Plan. Choose included cash/bank accounts and the forecast's end date.
   Each currency has its own projection. An unknown selected balance keeps the
   total unknown. Expectations do not change Accounts or recorded net worth.
2. Add a bill or expected income, with its account, date and repeat schedule.
   Look for the shortfall before later income; a positive ending balance does
   not remove that warning.
3. Open an occurrence. Record a receipt/payment only after it happened, review
   the actual account/date/amount and any balance-check coverage, then confirm.
   Alternatively, select an existing matching activity and confirm the link.
4. Inspect the original activity, correct it, or edit the expectation. Recorded
   occurrences stay linked to the same activity. A changed actual account needs
   review; a refund does not automatically reopen the paid bill.
5. Reopen the app and inspect Plan, Home and the affected account.

Monthly schedules preserve the intended day, clamping to the last day in a short
month. Twice-monthly dates that clamp to the same day create one occurrence.
The saved time zone owns the planning day. Forecast steps show individual dated
movements, with bills before income on the same date; this is a conservative
ordering, not a claim about the time of day a payment arrives.

## Restart while preserving records

Use the retained checkout. Do not run `configure`, `seed`, `reset`, or remove
Docker volumes. Skip a service command if its port is already owned by this demo.
Start the API and CAPTCHA bridge in separate terminals and keep them running:

```sh
cd /Users/garces/.codex/worktrees/connected-plan-home/private-alpha-next
python3 ios/scripts/auth/local_stack.py start --accounts --port-base 58600
python3 ios/scripts/auth/local_stack.py api --accounts --port-base 58600 \
  --accounts-enabled on \
  --python /Users/garces/.codex/worktrees/5a42/private-alpha-next/.venv/bin/python
```

```sh
cd /Users/garces/.codex/worktrees/connected-plan-home/private-alpha-next
python3 ios/scripts/auth/bridge.py --accounts --port-base 58600
```

Launch the retained app:

```sh
xcrun simctl boot 4E22655F-72DC-468F-AEBB-97FBDC58B514 # only if shut down
xcrun simctl launch 4E22655F-72DC-468F-AEBB-97FBDC58B514 local.argus.foundation
open -a Simulator
```

If sign-in is needed, this existing read-only Home/reopen check uses the ignored
fixture without exposing credentials or appending financial records. Launch the
app again after the check finishes:

```sh
cd /Users/garces/.codex/worktrees/connected-plan-home/private-alpha-next
python3 ios/scripts/auth/run-ui.py 4E22655F-72DC-468F-AEBB-97FBDC58B514 \
  --accounts --port-base 58600 \
  --only ArgusFoundationUITests/FinancialLoopUITests/testRetainedHomeSurvivesReopening
xcrun simctl launch 4E22655F-72DC-468F-AEBB-97FBDC58B514 local.argus.foundation
```

## Repeat focused acceptance

Run cases serially; they deliberately create uniquely named synthetic records.
The complete native case is:

```sh
python3 ios/scripts/auth/run-ui.py 4E22655F-72DC-468F-AEBB-97FBDC58B514 \
  --accounts --port-base 58600 \
  --only ArgusFoundationUITests/FinancialLoopUITests/testConnectedPlanRecordsLinksCorrectsAndReopens
```

`testPlanKeepsUnknownCurrencyAndLocalizedPresentation` verifies unknown USD and
Spanish/light presentation. `testPlanResponseLossRecoversOnceAfterRelaunch`
requires explicit `--response-loss-proxy` opt-in and an app configured for the
local test proxy58612. The proxy drops one response only after the API commits.
That case switches from owner A to B and back before retrying A's pending payment.
The normal retained demo uses direct API58600, without injected failures.

The independent real-HTTP journey is:

```sh
/Users/garces/.codex/worktrees/5a42/private-alpha-next/.venv/bin/python \
  scripts/verify_connected_plan.py ios/.build/accounts-local-58600/client.json \
  --output /tmp/connected-plan-http-proof.json
```

It checks the earlier shortfall, fulfillment, duplicate retries, corrections,
refunds, explicit linking, expectation edits, changed-account link review,
recurrence, unknown currency, identity isolation and fresh-session persistence.
It adds synthetic data; it does not replace or reset existing demo records.

## Delivery limits

This scope does not complete budgets, savings goals or debt-plan lifecycles.
They remain tracked in the MVEE manifest. The existing recording API does not yet
remove/restore activities; this lane makes no claim of that broader MVEE behavior.
Forecasts cover explicitly entered expectations and selected cash accounts;
missing bills and uncertain income are not an affordability guarantee. Currency
conversion and unresolved loan rules are not invented. No production changes,
signing, deployment or merge are included.
