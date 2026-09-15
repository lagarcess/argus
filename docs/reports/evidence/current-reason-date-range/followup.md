# Follow-up to the bounded measurement

The founder authorized fixes and a new proposal, not a paid rerun yet. The
original scorecard, diagnostics, and comparison remain unchanged in
`measurement/`. The fingerprint still names its prior baseline.

## Asset reason ownership

The captured diagnostic has `MRNA` resolved alongside
`provider_context_incomplete_asset_mentions`; the stage's required-field
calculation reintroduces `asset_universe` whenever that code survives. The code
comes from preflight completeness, not the reply model.

A provider-catalog reproduction exposes the disagreement: typed `@mrna` is
rejected while `MRNA` resolves. Preflight therefore marks the context incomplete,
while the main interpretation can still store resolved MRNA. The original paid
capture did not retain the raw preflight output, so the exact raw mention in
that call cannot be asserted. This deterministic reproduction follows the same
observed route and retains the original mention as provenance.

The shared symbol resolver now accepts mention/cashtag notation after structured
extraction and still requires provider resolution. It does not parse a user
sentence or bypass asset validation. At the provider-context owner, a complete
current resolution clears both its missing-field entry and stale incomplete
reason, including when the draft itself is unchanged. Ambiguity, omitted basket
members, and genuinely incomplete contexts still block; existing ownership
regressions cover these cases. The reply writer does not reconcile competing
facts itself.

## Correction to the Spanish probe interpretation

The original targeted probe recorded backend compatibility text, not the
frontend-rendered reply. Its claim of visible English on Spanish turn 1 was
therefore too broad. `ChatMessage` renders the typed degraded contract through
`chat-recovery-display.ts` and the selected locale. The new tests render the
committed probe through that exact display function in both languages.

There were still defects at that boundary. A date-window category used generic
unsupported-rule wording. Also, missing or malformed capital bounds returned
empty display text, causing `ChatMessage` to fall back to persisted prose. Date
recovery now names unavailable history in the locale; absent/invalid bounds
produce localized generic capital recovery. Valid numeric bounds keep their
existing exact rendering. No Spanish prose table was added to Python, and no
extra paid translation call was introduced.

New user-facing locale strings (not model-facing instructions):

| Key | English | Spanish |
| --- | --- | --- |
| `data_window_unavailable` | That date range is outside the available market history. Choose another date range. | Ese rango de fechas está fuera del historial de mercado disponible. Elige otro rango de fechas. |
| `starting_capital_unavailable_bounds` | That starting amount cannot be used for this test. Choose another amount. | No se puede usar ese monto inicial para esta prueba. Elige otro monto. |

## Fixture correction

Both newly added date cases had the same incorrect launch-date expectation;
the English case had stopped before reaching it. For this September 2026
acceptance run, both still require requested August 16–19 and now require the
effective August 17–19 window: August 16 is Sunday. They explicitly require no
assistant prose on the confirmation turn. The Spanish prose judge was removed
because a confirmation card carries no prose. A negative offered-response check
now fails if prose nevertheless appears.

These are intentional fixture changes after the failed measurement. The old raw
failures have not been relabeled as passes. The launch expectation is dated to
this September 2026 acceptance window; it must be reviewed before a future-year
run whose weekdays differ. The two requested-range cases continue to exercise
the current-year reading in English and Spanish.

## Integration and measurement validity

Latest integration `edeaffa9f6565e4750fa0685a050f10aefd6d718` was merged one-way as
`550317ac61c475a311c4ced7fc9b9a3b86ab18f0` before these fixes. Original lane base
remains `039189128ea6ffcf59be73f3564fd936f191f662`. Incoming money-question recovery
changes share interpreter, research, and localized recovery surfaces; the full
suite and next complete live run must cover that overlap. Existing paid results
remain historical failure evidence, not acceptance of this new tree.

No new model-facing instruction was added by this follow-up. The two lane
instruction strings remain exactly as recorded in README.md. Integration's
interpreter/recovery changes also travel in the candidate to be measured.

## Proposed rerun, awaiting go

One clean published head, all 73 cases, including both corrected date cases and
the six previously unmeasured research Agent cases. Compare every case and every
failed check to the scorecard named in the unchanged fingerprint, and also show
the delta from the first bounded run. Explicitly identify the two fixture
corrections; do not treat changed assertions as evidence of a product fix.

Use the acceptance run's accounting convention: reserve **$0.625 for each Agent
attempt**, including any fallback attempt. Six expected attempts reserve
**$3.75**. Retain that estimate for missing usage, timeout, or cancellation;
reconcile actual reported usage with the served model and tool usage when
available. Add the OpenRouter/Search charges and retained unknown-call reserves
to the same meter. The previous conservative non-Agent total was $2.906379,
putting the combined planning estimate at **$6.656379**.

The meter has a **$7 hard admission stop**: do not dispatch another paid request
unless its reservation fits. Run serially, retain charges for remotely continuing
cancelled work, and stop on an overrun or unpriced model rather than hide it.
The $0.625 allowance is the founder-requested estimate from the acceptance run,
not a provider-enforced invoice ceiling; actual late usage can revise it. No
extra diagnostic retry is proposed. No commits while the run is active.

Only refreeze if the completed case-by-case comparison establishes no regression.
Otherwise retain failures and stop. If Codex raises a second finding on the same
mechanism, stop and report instead of applying another fix.

## Free verification before publication

- The original repro tests failed before the changes: five provider/reason
  checks, four rendered fallback checks, and two fixture/no-prose checks.
- 45 focused backend ownership/state/date checks pass, including existing
  truncated-basket and ambiguous-asset safeguards.
- Full provider-free backend suite: **8680 passed, 604 skipped, one expected
  prompt-freeze failure**, with local environment overrides and provider
  credentials removed. The original `.env` link was restored after completion.
- Full frontend suite: **1985 passed**, two snapshots. Three old malformed-bound
  expectations were updated from empty text to the localized generic recovery;
  they still reject displaying the invalid bounds.
- Repository Ruff and merged-tree modularity pass. Python wheel and sdist build
  pass. Frontend production build passes; its sandboxed Turbopack attempt stalled
  and was stopped before the successful host-permission build. Exact published
  head and hosted CI/review outcomes will be recorded in
  the PR comment after those checks return.
