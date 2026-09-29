# Connected personal money recording

This native slice uses the existing registered Argus session and canonical
financial API. It establishes balances and records received income, spending,
owned-account transfers, credit-card payments and refunds. Accounts and Home
update from the same records, including corrections and balance-check coverage,
and preserve them across relaunch. It does not implement the rest of the MVEE.
The [execution manifest](../docs/specs/argus-execution-board.md) owns full coverage
and approval status; the [MVEE](../docs/specs/argus-minimum-viable-ecosystem-experience.md)
owns the approved experience.

The backend owns signed balances, currency precision, ownership shares, placement
against opening/check observations, and reconciliation. Swift only formats exact
wire amounts. Home keeps currencies separate and excludes unknown balances from
known subtotals. Recorded spending is not a claim of complete spending coverage.

## Configure an isolated local stack

Follow [native auth prerequisites](AUTH_SETUP.md). Allocate the existing local
ports to one stack owner; do not run competing auth and accounts stacks. From the
repository root, with no shared root environment files:

```sh
python3 ios/scripts/auth/local_stack.py configure --accounts
python3 ios/scripts/auth/local_stack.py start --accounts
python3 ios/scripts/auth/local_stack.py seed --accounts
python3 ios/scripts/auth/local_stack.py api --accounts --accounts-enabled on --python "$PWD/.venv/bin/python"
```

Run the existing local CAPTCHA bridge in its own terminal:

```sh
python3 ios/scripts/auth/bridge.py --accounts
```

The API must include the canonical financial migrations, including the financial
loop and personal-money activity/revision-integrity migrations. A `/health`
response alone is not proof that these migrations are present. The stack creates only synthetic identities in ignored local files.
Never copy passwords or tokens into configuration or committed evidence.

### Keep another demonstration running

Use a separate checkout and one `--port-base` value across all three launchers.
The allocation derives the Supabase project ID, ignored state directory, API,
database, CAPTCHA and recovery URLs. Existing commands retain their original
ports and state. Configuration refuses occupied ports or an existing stack;
restart reuses retained data and does not reseed.

For a second demo, reserve 58500–58511 and create a new owned simulator:

```sh
python3 ios/scripts/auth/local_stack.py configure --accounts --port-base 58500
python3 ios/scripts/auth/local_stack.py start --accounts --port-base 58500
python3 ios/scripts/auth/local_stack.py seed --accounts --port-base 58500
python3 ios/scripts/auth/local_stack.py api --accounts --port-base 58500 --accounts-enabled on --python "$PWD/.venv/bin/python"
# In another terminal:
python3 ios/scripts/auth/bridge.py --accounts --port-base 58500
python3 ios/scripts/auth/run-ui.py <new-owned-simulator-UDID> --accounts --port-base 58500 --only ArgusFoundationUITests/FinancialLoopUITests
```

State is `ios/.build/accounts-local-58500`; the local project is
`ios-accounts-58500`. The API uses 58500, Supabase 58501, Postgres 58502 and
CAPTCHA 58505. The ignored `ios/Config/Local.xcconfig` belongs to this checkout;
never copy another demo's fixture or overwrite its simulator. Restart only the
`start`, `api` and bridge commands as needed. Leave `configure` and `seed` for
first setup. No web server is needed for this accounts demonstration.

Run launcher isolation checks with:

```sh
python3 -m pytest ios/scripts/auth/test_local_stack.py -q --no-cov
```

## Verify

```sh
swift test --package-path ios/Packages/ArgusSession
python3 ios/FinancialModelTests/run.py
python3 ios/scripts/auth/run-ui.py <owned-simulator-UDID> --accounts --only ArgusFoundationUITests/FinancialLoopUITests
```

The model command compiles the actual app model sources in a disposable Swift
package. It covers uncertain-response replay, Home refresh races, identity
retirement, and placement corrections without modifying the signed project.

The UI journey uses the real local API and Postgres: unknown balances remain
unknown after spending; later balance establishment asks whether that spending
is included. A second journey checks account and Home changes after expense,
correction and balance check, then records spending already inside the checked
balance and confirms the original difference and remaining explanation. Reopening
must preserve the same account. A Spanish check covers the connected review copy.

The personal-money suite adds inspection and paired corrections, received-month
refund reporting, separate currencies, unknown balances and identity isolation.
An explicit local fault-proxy run verifies that a committed write whose response
is lost survives process restart and retries once with its original key. The
[personal-money evidence and restart instructions](../docs/reports/evidence/personal-money-recording/ios/README.md)
identify the retained simulator, source and completed acceptance.

Raw `.xcresult` bundles remain ignored because authentication diagnostics may
contain synthetic credentials. Promote selected screenshots, a short recording,
and a sanitized summary under `docs/reports/evidence/personal-money-recording/`.
The earlier loop retains its own evidence directory. Record the
native commit, backend commit, runtime, and the exact exercised journey. A skipped
live test is not a pass.

## Recovery and delivery limits

Network failures after confirmation retain the reviewed request and its
idempotency key for retry. Version conflicts require a fresh review. Expired
sessions return to existing sign-in recovery. Editing amount/date renews placement
review; inclusion choices can be corrected before confirmation. Backend rejection
still owns unsupported history placement, including checks before the latest
observation. That is a visible implementation limitation, not a new MVEE deferral.

Account creation remains the compact type, nickname, currency and optional balance
form. Saved-item details and balance provenance are separate. Local preferences
hold appearance only; session credentials use device-only Keychain; financial
records remain canonical server records.

Hosted migration, deployment, signing and physical installation require the
founder's reserved approvals. Simulator evidence proves a component checkpoint;
completion requires the founder's physical iPhone with their existing identity and
real data over the internet.
