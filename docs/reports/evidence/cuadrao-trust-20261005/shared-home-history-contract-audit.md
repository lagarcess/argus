# Shared Home history contract audit

Source-only audit, October 5, 2026. Integration inspected:
`13a1a339cbab1a3896e10779477658af63e062b3`. Recovered UI inspected at the
assigned immutable source `1f8a716e7cb89bb9e78f4575f39d7c8dca0790df` using
`git show`; its checkout has since advanced, so this report does not certify
that checkout's current head.

## Finding

Current Home amounts have a canonical read contract. Historical balance charts
and complete-period spending comparisons do not yet have a connected read
contract. A current known balance does not establish earlier balances, and a
balance check does not establish complete spending coverage.

The captain reports that #824's #838 rolling-30-day Upcoming and #839 movement
detail/swipes landed, while full history, insights, coverage and move-history
remain untouched. This report did not independently read GitHub. #824 remains
Counsel's presentation lane; SharedFoundations #820 read-contract coordination
remains with the root captain. Neither issue is closed by this audit.

## Locked behavior and current contracts

| Fact | Verified source at integration |
| --- | --- |
| No currency conversion or blended total; primary first; one chart/comparison currency | `docs/specs/argus-minimum-viable-ecosystem-experience.md:267-274` |
| Opening/check facts are distinct from activity; discrepancies stay visible; a known balance can coexist with incomplete transactions | MVEE `368-394` |
| Confirmed complete month with no spending is zero; missing coverage is Sin datos; earlier zero uses an amount difference | MVEE `885-887`; `docs/specs/argus-decision-log.md:248-258` |
| Monthly recorded-only spending uses an explicit reporting zone and half-open interval; refunds use return month; transfers/card payments excluded; loan costs count, principal excluded | `docs/API_CONTRACT.md:7250-7264` |
| Current positions use ownership shares; activity uses full amounts; archived accounts remain in summaries | API contract `7261-7264` |
| Observation coverage binds exact observation/activity revisions and retains earlier choices; it is not a whole-period completeness claim | `docs/DATA_MODEL.md:1963-1970`; `src/argus/domain/recording/loop.py:83-88,136-149` |

These are approved semantics, not proof of implemented historical charts.
`docs/DOCUMENTATION_AUTHORITY.md:18-30,68-83` keeps product direction, technical
contracts and implementation assignments with their separate owners.

## Narrow source owner map

| Owner/path | Existing truth | Missing surface |
| --- | --- | --- |
| `src/argus/domain/recording/loop_reads.py:148-248` | Current per-currency amounts, known/unknown counts, freshness, monthly spending, five recent activities | No historical points, gap/partial status or complete-period evidence |
| `src/argus/domain/recording/loop_schemas.py:187-225` | Home response, period and literal `recorded_only` coverage | No series/complete-period response |
| `src/argus/domain/recording/records.py:25-45`; `loop.py:15-100,102-149,152` | Dated opening/check/activity records, zones, revisions, author/recording provenance and reconciliation links | No historical aggregate projection or sampling policy |
| `src/argus/domain/recording/money_home.py:11`; `spending.py:19` | Reporting interval and canonical spending classification | No complete-period confirmation |
| `src/argus/domain/household/financial.py:110`; `projection.py` | Authorized activity-history and current-position readers | No authorized balance-series DTO; revision history is not chart history |
| `ios/Packages/ArgusSession/Sources/ArgusSession/FinancialLoopTypes.swift:222-279` | Current Home DTO, currency exponent, period and coverage | No connected balance/spending-series adapter |
| Recovered `ios/ArgusFoundation/Connected/ConnectedCuadraoBalanceOverview.swift:38-63` at assigned UI SHA | Canonical current amount, partial/unknown count, freshness and explicit unavailable-history state | Unconditionally renders chart placeholder; current facts alone cannot replace it with a line |
| `ios/ArgusFoundation/Cuadrao/CuadraoBalanceHistory.swift:27-49,70`; `CuadraoSpendingStory.swift:8-24` | Preview observation matching and example coverage | Preview fixtures and coverageStart are not production facts |

The recovered current header is already bound separately from history. Its
currency fallback at recovered file line 11 selects the first server row; C1's
primary/explicit-choice presentation work is separate from a history contract.

## Precise missing contracts

1. **Balance-series meaning.** Settle whether the chart shows recorded
   observations or reconstructed history using current revisions. Define
   sampling, gaps, partial account coverage, backdated corrections, timezone,
   account inclusion and historical shares/types. Existing dates and provenance
   permit some grounded observations; they cannot prove intervening balances or
   balances before the first anchor. `loop.observations` uses current opening
   revision and checks; it is not an as-of replay engine.
2. **Complete spending coverage.** Define who confirms completeness, for which
   account/currency/period, with provenance and correction invalidation. The
   existing `included` fact answers whether an activity is included in a balance
   observation. It cannot establish a zero spending month. Monthly sum zero under
   `recorded_only` means recorded sum zero, not confirmed complete zero.
3. **Authorized history scope.** The adapter must derive from current access
   owners and the applicable frozen/pre-move history rules. Settle how moved,
   deleted, revoked and frozen accounts appear; do not replay unavailable facts
   from native cache or derive historical permissions from current membership.
4. **One shared read shape.** Define currency/exponent, reporting zone, interval,
   authorized included accounts, points with source references, gaps/unknowns,
   freshness and comparison eligibility. The native chart must render that
   contract rather than rebuild a financial ledger.

## Bounded next units

Current header/currency presentation can use existing summaries. After the
captain settles the missing contract, separate the canonical history reader/DTO,
complete-period coverage contract, and native adapter into small owned units.
Reuse existing positions, spending classification and authorization. Acceptance
should cover known zero versus missing coverage, zero comparisons, corrections,
archive/move/access loss and exact currency precision.

Recommendation for the current state: keep the current header visible and show
history as unavailable until its contract is settled. Label spending as
recorded-only until complete-period evidence exists. This is temporary truthful
status, **not approval to remove required history, insights or comparisons**.
No new product choice, implementation assignment or release waiver is created.

## Proposed executable handoff, pending founder choice

The genuine product question is: **Should the first connected history show only
dated recorded observations, or reconstruct past balances from today's corrected
records?** Recommend observation-only first. It exposes facts the existing owner
can identify without inventing balances between checks. This recommendation does
not settle the question or fulfill the full history/insights/move-history scope.

Smallest proposed read shape, illustrative only; field names and endpoint are not
approved. Reuse existing minor-string/exponent and period conventions from
`loop_schemas.py:187-225`, opening provenance from `records.py:25-42`, and
check/observation identity from `loop.py:62-100`:

```text
history {
  meaning: "recorded_observations",       // proposed, requires selection
  scope: { kind, authorized_account_ids },
  period: { time_zone, start_at, end_at_exclusive },
  recorded_at,
  currencies: [{
    currency, currency_fraction_digits,
    current: { net_worth_minor, known_accounts, unknown_accounts, as_of },
    observations: [{
      account_id, record_id, revision, type,  // opening/check/value-update
      amount_minor, as_of, time_zone, recorded_at
    }],
    points: [{
      as_of, net_worth_minor, account_ids,
      known_accounts, unknown_accounts, partial,
      sources: [{ account_id, record_id, revision }]
    }],
    gaps: [{ start_at, end_at_exclusive, reason }]
  }]
}
```

All money fields are exact signed minor-unit strings. Each point uses one
currency/exponent. Current remains the current projection, not a fabricated
historical point. No interpolation, forward-fill, back-projection or future
points. An account observation alone must not become a full-space total. A
point may sum only compatible observations at its declared time; absent account
facts remain absent, with explicit partial/unknown state. If no defensible
aggregate exists, return observations/gaps and no aggregate point. Point
eligibility and gap boundaries must be specified in contract tests before code.
Revision references describe the selected record facts; this shape does not
promise a historical "what the app knew then" replay.

Authorization is re-evaluated by existing server access owners on every read.
The household reader already resolves scope inside a transaction
(`household/financial.py:110-125`); use that boundary rather than native cached
permission. Pre-move/frozen/deleted-owner history remains dependent and blocked
until its spaces/history owner supplies an accepted projection rule. Do not
silently include those facts or claim that a personal-only adapter completes
household history. Account kind/share treatment must also be explicit before
aggregation; current attributes cannot silently rewrite old observation meaning.

Keep spending on the existing `coverage:"recorded_only"` response. Do not add a
completeness store in this unit and do not infer complete zero from a sum, an
empty activity list, an opening or a check. Known-zero comparisons remain
blocked until a separate accepted complete-period contract supplies that fact.

Ownership and order:

1. Root coordinates one canonical read contract with the existing Recording
   and authorization owners. Founder selects the history meaning. Shared money
   owner work is serial; do not create a competing ledger or spending classifier.
2. First implementation unit, only after that choice: add failing contract tests
   for source revisions, dates/zones, exact currency precision, unknown/partial
   gaps, no invented points, corrections, archive and denied/revoked access.
   Add real-PostgreSQL tests for owner/scope filtering and canonical revision
   readback; then implement the bounded reader/DTO. No provider or device work
   is needed to establish these server contract facts.
3. Counsel owns native adapter/layout after the DTO is accepted. Render its
   states through recovered components and clear inspection on currency/scope
   changes. Do not move financial reconstruction into chart code.

C1 remains current Home currency ordering/selection from existing summaries.
C3 remains the separate connected Plan forecast consumer of existing forecast
truth; it supplies no historical balance or spending completeness. Neither
closes this history gap. This is a proposed handoff, not API implementation,
founder approval, full-scope acceptance or release evidence.

## Limits

Source inspection only. No customer/account records, phone, Mac/device tooling,
environment, database, provider or service reads. No tests, build, physical-device
or delivery claim. Only this report was written; no code edits, Git commit,
push, PR creation, merge or deployment. No child agents or running resources.
