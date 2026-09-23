# Argus, local finance workspace

Argus combines a money view with its familiar conversation, composer and
Omnisearch. Inspect a financial record, ask about it, confirm a proposed change
and reopen the same artifact from either surface. Spanish comes first; English
is available. The cream and forest palette uses the existing Argus fonts,
interaction patterns and responsive navigation.

The guest entry offers an isolated prepared household or an empty workspace.
The larger demo profile has 14 accounts and 13,680 Faker-generated transactions
over 24 months, including salaries, refunds, transfers, pending entries and four
currencies. Prepared questions and artifact confirmations work without an API
key. Free text requires an explicitly configured model; the demo does not fake
language interpretation.

## Run locally

Requires Python 3.10 or newer, Bun, and a browser. From `money-view/`:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
cd web
bun install --frozen-lockfile
bun run build
cd ..
.venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8012
```

Open [Argus on port 8012](http://127.0.0.1:8012). Explore the guest demo, start
with an empty workspace, or open Sign in and select a local demo profile. Use
the password `Clara-demo-2026!`. The profiles include owner, editor and viewer
roles, plus a separate household for isolation checks. These are deliberately
public fixture credentials, not credentials for a hosted service.

The API serves the built app and stores data in `.local/clara.sqlite3`.
`CLARA_DATABASE_PATH` selects a different local database. The existing `CLARA_*`
configuration names and fixture password remain compatible. The local app reads
no `.env` and does not import the production application bootstrap. Pure Argus
calculators are generated from hash-pinned source files; the local LangGraph
planner uses explicitly configured OpenRouter transport. Do not edit or reuse
parent `.env` files.

For frontend development, keep the API running and run this in another terminal
from `money-view/web/`:

```sh
bun run dev
```

Open [the development app on port 5178](http://127.0.0.1:5178). Vite proxies
`/api` to the loopback API on port 8012.

## Explore the platform

| Page | Local workflows |
| --- | --- |
| Overview and accounts | Inspect dated balances, net worth and spending by currency; review connections and failed refreshes. |
| Transactions | Search and filter the full ledger, page through results, edit categories, split transactions, and map CSV/TSV statement columns, review duplicates and confirm a frozen import before writing. |
| Planning | Set budgets, record recurring bill payments, allocate goals, and save life-event or retirement scenarios with immutable assumptions and results. |
| Investing | Inspect holdings, allocation and performance; preview and confirm simulated orders, bundles and recurring plans in a separate fictional cash book. |
| Services | Explore credit and payoff calculations, tax organizers, estate records, local appointment reservations, memberships and employer benefits. |
| Settings | Manage local sessions, passwords, profiles, language, appearance, household roles, confirmed memories, history, export, reset, account deletion and locally saved feedback. |
| Chat and Omnisearch | Read owned records, use Argus calculations, confirm typed artifact changes, pin/rename/archive conversations and reopen exact records. Export complete bounded conversations; older receipts remain accessible. |
| Deposits | Edit an amount and horizon, confirm, calculate, inspect dated receipts, save, and compare before/after results when a simulated publication changes. |

Financial totals derive from the account and transaction ledger. Currencies stay
separate without a dated conversion quote. Simulated investment cash and orders
do not change linked-account net worth. Household records are scoped to the
active session, and viewer roles cannot change shared financial records.

The assistant explains stored facts and computed results. With no model
configuration, free-text interpretation is explicitly unavailable. Prepared
questions use typed actions; the demo does not guess intent from keywords.

## What is simulated and what is verified

The demo uses fictional identities, institutions, account activity, deposit rates,
fees, inflation, investment prices and service workflows. Receipts identify
synthetic observations and their dates. User records carry recording or effective
dates; a retrieval timestamp never substitutes for a publisher's date.

Local confirmations create local records only. No real order, money movement,
payment, invitation, appointment booking, tax filing or legal submission occurs.
There is no public hosting or outbound email service. Feedback stays local.

One explicit Alpaca adapter call was verified on September 21, 2026: one
read-only HTTP GET for `SPY` using the `iex` feed, with a market observation dated
September 18. It used an isolated verification database. The ordinary demo
database remains seeded with fixtures. This verifies that bounded read, not
broker execution or broad market-data coverage. See the
[Alpaca receipt](docs/evidence/scale/alpaca-readonly.json) and
[investing adapter contract](docs/platform-api/investing.md).

Live SB and BCRD bank/inflation loading remains unverified. SB raw records cannot
become calculation-ready rates without verified maturity, publication dates and
rate semantics. BCRD's machine schema and real-data reuse permission remain
unresolved. Missing credentials or metadata never silently become fixture data.
See [provider feasibility](docs/provider-feasibility.md).

No live language-model evaluation has been completed. The local structured
OpenRouter planner reads `CLARA_LLM_API_KEY`, `CLARA_LLM_BASE_URL`
and `CLARA_LLM_MODEL` from explicit process configuration. It interprets the
question once; deterministic domain code owns financial values and calculations.
The transport explicitly disables SDK retries, ambient tracing and redirects.
Jev was investigated as a classification candidate; it is not enabled and no
application latency improvement has been measured. See [Jev findings](docs/experience/JEV.md).
Shared semantic admission counts attempts and concurrent calls. Those limits
are not dollar budgets, and provider pricing is reported as unknown.

## Data loading, jobs and backups

Pages and calculations read persisted data. They do not poll vendors. Deposit
publications, fixture price refreshes and recurring investment work use the
shared durable SQLite queue. API processes claim work through shared limits and
leases. Failed loads retain the last good data.

From `money-view/`, submit and wait for a fixture publication:

```sh
.venv/bin/python -m server.jobs --database .local/clara.sqlite3 --provider fixture load --scenario baseline
```

The CLI uses the same queue as HTTP demo controls. Supply `--load-id` after
`load` to replay one logical attempt. Fixture scenarios are `baseline`,
`same_winner`, `leader_changed`, `inflation_crossed`, and `failure`. A publication
rechecks saved deposit decisions without a model call and preserves each original
receipt. No cron entry or external scheduler is installed.

Create a local SQLite backup and restore it to a new file:

```sh
mkdir -p .local/backups
.venv/bin/python -m server.platform.storage_ops backup .local/clara.sqlite3 .local/backups/clara.sqlite3
.venv/bin/python -m server.platform.storage_ops restore .local/backups/clara.sqlite3 .local/clara-restored.sqlite3
```

Destination files must not already exist. Keep the adjacent `.manifest.json`
with the backup. Restore validates integrity and recorded row counts; it does
not replace the running database. Keep backups outside publicly served folders.
Local backup support does not provide encrypted off-host storage or disaster
recovery operations.

Household JSON export has one shared budget across domains: 50,000 source rows
and 32 MiB of serialized source-row bytes. Exceeding either returns
`household_export_too_large` with HTTP 413 and no partial download. See the
[identity contract](docs/platform-api/identity.md) for export and deletion rules,
and the [runtime contract](docs/platform-api/runtime.md) for queue, request,
login and semantic limits.

## Deposit calculation boundaries

The deposit comparison supports bank savings and certificates. It uses simple
annual ACT/365 interest, no rollover or currency conversion, and a disclosed
constant annual inflation scenario. Known sourced fees are included; unknown
fees and taxes are excluded. Certificates must match the requested horizon.
Decimal math retains precision until presentation. Each result includes the
confirmed current rate or explicitly confirmed zero-interest cash baseline.

The calculation accepts amounts from 0.001 to 1 trillion and verified annual
fees from zero to 1 trillion, with at most three decimal places. Annual rates
and inflation must be greater than -100% and at most 1000%, with at most six
decimal places. Unsupported magnitudes fail validation. Receipt substitutions
use approximate signs because displayed figures are rounded; stored calculations
retain full precision.

The top row means highest modeled end value among comparable rows. It is not
investment advice or a statement about an actual bank quote. Real regulator
rates describe averages paid on balances; a branch may quote something different.

## Verification and capacity

Run deterministic checks from `money-view/`:

```sh
.venv/bin/python scripts/sync_argus_core.py --check
.venv/bin/python -m pytest -c pytest.ini tests -q
.venv/bin/python -m ruff check server tests scripts
cd web
bun run build
bun run test:unit
bun run test:e2e
```

Browser checks use isolated loopback processes, the actual API and temporary
SQLite data. Browser installation may require `bunx playwright install chromium`
once. The [experience verification](docs/evidence/experience/verification.md)
records the exact local evidence and remaining provider/hosting limits. The
[experience plan](docs/experience/PLAN.md) tracks private delivery; the
[prior PR audit](docs/PR_REVIEW_AUDIT.md) records the earlier clean review loops.

Argus supports local authenticated households and multiple processes sharing
one SQLite database on one host. That does not qualify it for public hosting.
The [scale design](docs/SCALE_DESIGN.md) defines the proposed 10,000-monthly-user
workload; [scale evidence](docs/SCALE_EVIDENCE.md) separates local measurements
from remaining qualification. Full retention volume, sustained heavy-household
traffic and the target hosting hardware still require acceptance evidence.
Monthly active users are not simultaneous connections.

All delivery remains in the isolated Argus finance lane. The only authorized PR target
and merge destination is `codex/money-placement-pilot`. There is no merge to
`main` or `codex/private-alpha-next`, deployment, production change, Supabase
connection or migration in this work.

## Experience implementation

The [experience plan](docs/experience/PLAN.md), [architecture](docs/experience/ARCHITECTURE.md),
[presentation reuse](docs/experience/REUSE.md) and [calculation provenance](docs/experience/CORE_REUSE.md)
record the local integration choices. Guest workspaces expire after 24 hours unless
claimed locally. Drafts are scoped to the user, household and data generation.
Only CSV/TSV statements are supported; PDF, spreadsheets and images are rejected
explicitly. File contents never become model instructions.
