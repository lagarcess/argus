# Clara implementation plan

Standalone money view, founder-amended 2026-09-20. This plan supersedes the
earlier Argus feature-lane brief. Execution is delegated to bounded workers;
the captain owns contracts, integration, verification, review and cleanup.

## Outcome and boundaries

Spanish-first money home with embedded chat and English parity. Complete local
demo: state money and horizon, confirm, compare sourced computed values, save,
publish a changed fixture through the data job, receive a notice, open the
saved answer with before/after receipts. All demo institutions/data are fake.

Everything is contained in `money-view/`. No Argus runtime imports, production
access, main/integration merges, deployment, .env writes, or Supabase migration
execution. SQLite initializes a new local application database only. No feature
flag, Argus docs sync, modularity budget, or model scorecard applies. No provider
or model credentials are read from the parent repository.

Private PR base: `codex/money-placement-pilot`; implementation branch:
`codex/money-placement-pilot-impl`. Both start from integration
`708864ef76961df2767d7e09c2fbf5f9812179c7`. PR review is authorized. Never target
`main` or `codex/private-alpha-next`.

The private base excludes only these two throwaway branches from the parent
Argus CI, which otherwise runs disposable Supabase migrations on every codex
push. The implementation adds a dedicated SQLite-only app workflow. This
branch-local exclusion must not be promoted to the protected branches.

## Architecture and synthesis

Use candidate A's immutable comparisons, atomic dataset publication and guarded
confirmation. Graft candidate B's single home projection and derive notices
from changed check records rather than maintaining a competing notice table.
Reject fixed country enums, `offer` terminology, fabricated source dates and
compound reinvestment assumptions. Use Python Decimal and simple annual ACT/365
fixture rates. React formats server-owned results, never calculates rankings.

Three substantive owners: pure calculation, complete dataset publication, and
placement lifecycle. Transport is FastAPI, persistence SQLite, UI React/Vite.
The independent candidate review and verified provider research are preserved
in `docs/architecture-review.md` and `docs/provider-feasibility.md`.

## Data contract

All JSON uses snake_case. Decimal values cross the API as strings.
All immutable Pydantic boundary models forbid extra fields and nonfinite values.

`Source`: `{id, title, url, published_on, retrieved_at, kind}`. Dates are ISO.
`kind` is `synthetic` or `published`; `published_on` must exist before a rate or
inflation enters a calculable dataset. Synthetic dates are simulated publication
dates of our fixture documents, never represented as real regulator releases.
User input provenance is separate: `{kind: 'user', recorded_on}`. A baseline
assumption is explicitly confirmed and labeled; it is not a regulator quote.

`DepositRate`: `{id, country, institution, product_type, currency, annual_rate_pct,
rate_basis, term_days, source, annual_fee, fee_source}`. Product is `savings` or
`certificate`; rate_basis is `simple_annual`; savings has no fixed maturity,
certificates must exactly match requested horizon. `annual_fee`/`fee_source` are
nullable together; unverified fees and taxes are excluded and disclosed.

`InflationRate`: `{country, currency, annual_rate_pct, source}`. Its reference
basket must match the calculation currency. No FX assumptions or conversions.

`RateDataset`: `{id, country, label, rates, inflation, published_on, synthetic}`.
`inflation` is a list so one country may have explicitly modeled currency baskets.
The id is a content hash excluding retrieval timestamps. Publication is all or
nothing; invalid/empty/incomplete loads retain the previous dataset.

`PlacementInputs`: `{amount, currency, horizon_days, country,
current_annual_rate_pct}`. Amount positive, finite, at most 1e12; days 1..3650;
ISO country/currency syntax only in the core, supported values come from data.
Current rate nullable means a disclosed zero-interest cash baseline at confirmation.

`ComparisonResult`: `{id, inputs, dataset_id, created_at, input_source, rows,
winner_ids, inflation, assumptions, synthetic}`.
`rows[]`: `{id, institution, product_type, is_baseline, annual_rate_pct,
end_value, effective_annual_rate_pct, real_value, interest, fees,
source, formula}`. Baseline source is the user input/confirmed assumption receipt;
every other row source is the dated rate Source. Each row uses the result's dated
inflation receipt as well. `formula` carries the explicit values/steps for the
receipt drawer; it is structured data, not model-generated math.

Calculate using high-precision Decimal:
`t = horizon_days / 365`, `interest = amount * annual_rate_pct / 100 * t`,
`end = amount + interest - verified_annual_fee * t`,
`effective_annual = ((end / amount) ** (1/t) - 1) * 100`,
`real = end / (1 + inflation_pct/100) ** t`.
The inflation assumption is held constant, explicitly an illustration, not a
forecast. Round once in the response presenter using currency minor units;
compare unrounded results. Monetary display uses copied Argus two-digit pattern
with ISO minor-unit exceptions such as JPY (0), KWD (3). No imports from Argus.
Notice ranking uses the same calculator and full tied-winner set, including cash.

## HTTP interface (captain-owned contract)

`GET /api/home` returns `{demo, interpreter_mode, countries, examples, source_status,
saved, notices}`. `countries[]` is `{code, name, currencies}`. Country names are
display data; country handling is never inferred from UI language.
`examples[]` is `{id, messages: {'es-419': string, en: string}, inputs, source}`.
Home shows an explicitly labeled sample balance from an example, not a fabricated
account balance. There are no calculated result figures before confirmation.

`POST /api/interpret` body `{message, locale, demo_example_id?}` returns
`{status, confirmation?, code?, missing_fields?}`. Status is `confirmation`,
`needs_input`, `unsupported`, or `model_unavailable`. Confirmation is
`{id, inputs, dataset_id, created_at, expires_at, assumptions, synthetic}`.
The model owns request meaning and extracts only these inputs. A schema-validated
deposit-only intent is required. No regex/keyword/language intent routing.
Demo replay uses an explicit example id and verifies the submitted example text;
an edited example cannot retain its recorded interpretation. Free text without
a live model gets an honest unavailability code, never guessed numbers.

`POST /api/confirmations/{id}/compute` body `{inputs: PlacementInputs}` returns
`ComparisonResult`. User may edit amount/horizon/currency/country/current rate on
the confirmation. Validate supported dataset and expiry. Compute only after this
action. Same confirmation+inputs replay returns the same comparison; a changed
body after consumption returns 409. Use the pinned dataset shown at confirmation.

`POST /api/comparisons/{id}/save` returns `SavedDecision`, idempotent by comparison.
`SavedDecision`: `{id, comparison_id, created_at, baseline, latest, checks}`;
baseline and latest are ComparisonResult. Checks include unchanged/failed records.
`GET /api/decisions/{id}` returns SavedDecision. Unknown ids are 404.
`GET /api/notices` returns `{items: Notice[]}`.
`Notice`: `{id, decision_id, created_at, reasons, before, after, read_at}`.
Notices are projections of checks with nonempty reasons, with a read timestamp on
the same row. `POST /api/notices/{id}/read` marks read, idempotently.
`GET /api/sources/{id}` returns a fixture/published source document with dated
raw inputs and synthetic label. A receipt URL never claims a fake regulator fact.

`POST /api/demo/events` body `{scenario}` returns 202 `{load_id}` and schedules
the local fixture job after responding. Scenarios: `same_winner`,
`leader_changed`, `inflation_crossed`, `failure`. UI polls home for terminal
load state. This invokes the same loader/check code as the scheduled CLI.
`source_status`: `{state: ready|loading|stale|unavailable, last_success_at,
last_attempt_at, error_code, dataset_id, load_id}`.
Errors are JSON `{code, detail?}` with localized frontend code mapping.

## Persistent behavior

SQLite owns datasets, deposit_rates, inflation_rates, load_attempts,
confirmations, comparisons, saved_decisions and decision_checks. No redundant
latest-result owner: derive from latest successful check or original comparison.
Checks persist before/after comparison ids, reasons and read_at. Atomic load
publication/check transactions and unique load/check keys make retries safe.
Each logical load attempt is recorded, including unchanged and failure. Failed
loads and failed rechecks never replace the last successful result. Never notify
for an unchanged winning set. Notify for a changed full top set or inflation
crossing from at/below to above the person's stated current rate (if present),
otherwise the saved leading deposit's effective annual rate. Store that reference
in the check so the notice can explain exactly what crossed. No model in jobs.

The app is a local single-user demo bound to loopback. It makes no production
auth claim. Document that hosted identity/ownership is not implemented.

## Provider boundary

`RateProvider.fetch(country: str) -> RateDataset` is the provider-agnostic seam.
Fixture provider implements two countries, DO and a clearly fake second country.
Core cannot contain DO/DOP/es-specific rules. SB adapter must parse documented
wire fields faithfully (including `tasaPrimedioPonderadoPorBalance`), support
bounded pagination, and keep missing maturity/publication/rate semantics explicit.
It cannot return calculation-ready data without verified evidence. Missing key
fails before a request; no fallback to fixtures. BCRD adapter remains unavailable
with a precise reason until its schema is known. Do not invent an endpoint.
No US provider implementation; document the interface seam for a future US source.

## Copy and visual design

Use `docs/design-concept.png` / `visual-design.md` for layout, corrected to the
Dominican pilot and actual backend-computed fixture figures. Working brand: Clara.
Home has money summary and source context, results space, saved notices, embedded
chat. A single result component renders current, saved and before/after rows.
ES default, EN available; selected locale persists locally. No core locale logic.
Every response shows: regulator averages may differ from a branch quote, and this
demo uses synthetic data. Use `tasa promedio pagada` / `average rate paid on balances`.
No advice/recommendation framing, no institution offers/pays wording, no em dashes.
Only savings/certificates; funds, securities, AFIs and trading are excluded.
Every financial number has accessible source/date context; calculated figures link
to rate, inflation and user-input receipts. Pure UI counts are not market claims.
Mobile 390px and desktop 1440px must work, controls labeled, keyboard usable.

## Tasks and ownership

- [ ] 1. Domain worker: `server/models.py`, `calculator.py`, `providers.py`,
  `fixtures.py`, `tests/test_domain.py`, `tests/test_providers.py`. Typed receipts,
  two-country fixtures, math/currency/fees/inflation, real-source fail-closed parser.
- [ ] 2. Service worker: `server/store.py`, `service.py`, `app.py`, `jobs.py`,
  `tests/test_service.py`, `tests/test_api.py`. Durable full flow, confirmations,
  saved history, recheck notices, loader CLI/background job. Must consume domain
  contract. No live data/model calls during implementation/tests.
- [ ] 3. Interpreter worker: `server/interpreter.py`, `tests/test_interpreter.py`.
  Fixture replay + optional structured semantic model adapter via explicit process
  config only. No dotenv or inherited Argus API keys. Live adapter not invoked.
- [ ] 4. Web worker: `web/` except captain-owned build config. React components,
  complete bilingual UI, receipt drawer, correct backend actions, before/after,
  pending/error/empty states. No frontend calculation or internal fake API store.
- [ ] 5. Captain: dependency/build config, isolated run scripts, README, synthesis,
  integration, browser tests, independent review/fixes, GitHub PR and Codex review.

Workers are not alone. Never revert another worker's edits. Only captain stages
and commits to avoid shared-index races. Use shared interfaces, not shared file
writes. A worker reports files, tests, risks, then stops; no hidden follow-up.

## Verification and stop conditions

- Pure tests: arithmetic, one-time rounding, inflation/negative real returns,
  currency digits, fees, terms, provider-neutral country, unknown provenance,
  incomplete/invalid load, last-good retention, no key/no requests.
- API/DB: complete flow, no pre-confirm compute, retry/tamper/expiry, immutable
  original, same winner silent, changed winner notice, inflation crossing,
  duplicate/late loads, simultaneous checks, failure retention, reload persistence.
- UI: ES/EN desktop plus mobile, actual local API and SQLite (no model/network),
  click through confirmation/save/change/notice/before-after, source drawer and
  error states, screenshots committed under `money-view/docs/evidence/`.
- Copy scan bans forbidden public wording and em dashes in both catalogs.
- Build/typecheck, focused tests, isolated CI job for this app, independent review.
- Stop rather than fabricate missing real-provider evidence. Report live SB/BCRD,
  arbitrary real-model interpretation and hosted multi-user operation unverified.
- No paid model calls, real provider loads, deployment or shared database actions.
