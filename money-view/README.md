# Clara

A standalone, local money view for comparing bank deposits with visible math
and dated receipts. Spanish opens first; English is available in the header.
The demonstration uses fictional institutions, synthetic rates and inflation,
and prepared example conversations. No API key is needed.

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

Open <http://127.0.0.1:8012>. The API serves the built app and stores local data
in `.local/clara.sqlite3`. It reads no `.env` and imports no Argus runtime.
`CLARA_DATABASE_PATH` can point to a separate SQLite file.

For frontend development, run the same API and `bun run dev` in `web/`; open
<http://127.0.0.1:5178>. Its `/api` proxy points only to the loopback API.

## Walk the demo

1. Select the prepared Dominican Republic example inside the chat.
2. Send it, inspect or edit the amount, currency, horizon and current rate,
   then confirm. No comparison computes before confirmation.
3. Inspect the comparison and open a source receipt or calculation detail.
4. Save the comparison. Reloading keeps it in **Guardados / Saved**.
5. Simulate a publication using the demo controls. A change that preserves
   the leading option is recorded quietly. A changed leader or an inflation
   crossing creates a notice.
6. Open the notice to compare the prior result with the new result. The
   original saved receipt remains unchanged.
7. Simulate a failed load: the source status reports the failure while the
   last good data remains available.

The interface identifies all synthetic figures and simulated publication
dates. User-entered inputs instead carry their confirmation date. A real
publisher's retrieval time is never substituted for its publication date.

## Data loading and scheduling

User calculations read the database. They never fetch rates or inflation.
The same loader serves a scheduled command and the asynchronous demo controls:

```sh
.venv/bin/python -m server.jobs --database .local/clara.sqlite3 --provider fixture load --scenario baseline
```

Example future cron schedule: `0 7 * * *`, one load daily at 07:00 in the cron
host's timezone. Set the host timezone explicitly; this repository does not
install a cron entry. Use absolute paths for the interpreter, app directory
and database. A successful publication atomically records rates and inflation,
then rechecks saved decisions without a model call. A failure records a load
attempt and retains the prior publication. Repeat attempts are safe.

Fixtures support `baseline`, `same_winner`, `leader_changed`,
`inflation_crossed`, and `failure`. The second synthetic country demonstrates
that the interface and arithmetic do not depend on the Dominican Republic.

## Optional language model

The seeded demo replays an explicitly selected example's structured reading.
It does not interpret arbitrary text. Editing the example clears that replay
identity, so the app cannot silently apply someone else's amount or horizon.

An optional OpenAI-compatible structured-output interpreter reads ordinary
language by meaning. Supply these only as process environment variables:

- `CLARA_LLM_API_KEY`
- `CLARA_LLM_BASE_URL`
- `CLARA_LLM_MODEL`

No parent-repository key is reused. The interpreter extracts deposit intent and
user inputs, never rates, rankings or computed results. Confirmation, data
selection, calculation and notices remain deterministic. Live model behavior
is not certified by the fixture demonstration.

## Real data: deliberately incomplete

The SB adapter documents and validates the actual public API wire fields,
including their spelling. However the public schema lacks maturity and
publication date, and does not establish rate units/annualization. Its raw
observations cannot become calculation-ready rates without those facts.
BCRD's inflation API schema requires access that is not available here.
Missing credentials or metadata never silently fall back to fixtures.

See [provider-feasibility.md](docs/provider-feasibility.md) for verified source
links, authentication, schema and gaps. A future SB key belongs in the explicit
provider configuration, not a committed file. No live SB/BCRD load was verified.
Reuse permission must be resolved before displaying real regulator data to users.

The provider protocol is the US extension point. Add a provider returning the
same validated country/currency/source/rate/inflation contract and test it through
the same loader. No US provider or US market-data behavior is implemented.

## Calculation and product boundaries

Bank savings and certificates only. The modeled comparison uses simple annual
ACT/365 interest, no rollover or currency conversion, and a disclosed constant
annual inflation scenario. Known sourced fees are included; unknown fees and
taxes are excluded. Certificates must match the requested horizon. Decimal math
keeps precision until the presentation boundary. Each result includes a baseline
for the confirmed current rate or explicitly confirmed zero-interest cash.

The calculation boundary accepts amounts from 0.001 to 1 trillion and verified
annual fees from zero to 1 trillion, with at most three decimal places. Annual
rates and inflation must be greater than -100% and at most 1000%, with at most
six decimal places. Unsupported magnitudes fail validation instead of producing
overflow or silently rounded inputs. Receipt substitutions use approximate signs
because displayed figures are rounded; stored calculations retain full precision.

The top row means highest modeled end value among comparable rows. It is not a
recommendation or a statement about a bank's actual quote. Real regulator data
describes average rates paid on balances; a branch may quote something different.

This is a single-user local pilot. Hosted authentication, authorization,
multi-instance operation and production deployment are not implemented. No
Supabase connection or migration is needed or applied.

## Verify

```sh
.venv/bin/python -m pytest -c pytest.ini tests -q
cd web
bun run build
bun run test:e2e
```

Browser tests start isolated local processes and exercise the actual API and
SQLite database. See [the build plan](docs/BUILD_PLAN.md) for ownership and
acceptance, and `docs/evidence/` for the final verification report/screenshots.

Backend checks cover interrupted-job recovery, per-attempt CLI exit codes,
immutable user-input dates during rechecks, verified zero-fee receipts, and
numeric boundary errors. The browser suite also rejects an edited prepared
message honestly and completes the same flow for the second country.

All work stays on the isolated lane and its private PR target. Nothing merges
to `main` or `codex/private-alpha-next`; nothing deploys.
