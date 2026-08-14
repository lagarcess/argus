# Issue #455 evidence: DCA capital semantics and the word "cadence"

Lane branch `claude/issue-455-dca-capital-semantics`, based on
`codex/private-alpha-next` at `3602ca16` (the merge of PR #487).

## What the browser shows

The card rendered in these captures is not hand-written. It is
[`dca-confirmation-card.json`](./dca-confirmation-card.json), produced by running
the real `confirm_stage` on the founder's own example, a plan that buys $200 of
Coca-Cola every month, and rendering the result through
`runtime_confirmation_card`. The Playwright spec
`web/e2e/issue-455-dca-capital-surface.spec.ts` serves that exact file to the
app, so what the browser renders is backend truth rather than a fixture that
agrees with it today.

The first version of these captures was wrong, and the founder caught it by
looking at the pictures. That fixture was built by hand with a stub
`launch_payload` of `{"sizing_mode": "capital_amount"}`, which failed
`validate_confirmation_execution_payload`, so every screenshot showed a
`needs_change` card with no Run button, a state no user sees for a valid plan.
The card is now generated through the stage itself and is `ready_to_run` with
`run_backtest` first.

| File | What it shows |
| :--- | :--- |
| `browser/card-en-desktop.png` | `Ready to run`, `Run backtest` first, and two money rows: `Contribution $200 monthly`, `Starting capital $0` |
| `browser/card-en-phone.png` | Same two rows at 390px |
| `browser/card-es-419-desktop.png` | `Aporte $200 cada mes`, `Capital inicial $0` |
| `browser/card-es-419-phone.png` | Same two rows at 390px |
| `browser/edit-en-desktop.png` | The edit drawer: exactly two fields, period inline on the contribution |
| `browser/edit-en-phone.png` | Same drawer at 390px |
| `browser/edit-es-419-desktop.png` | `Capital inicial` and `Aporte` with `cada mes` inline |
| `browser/edit-es-419-phone.png` | Same drawer at 390px |

Every capture asserts, in the same test that takes it, that the card is
`ready_to_run` and shows its Run button; that the rendered card contains none of
"cadence", "cadencia", or "frecuencia"; that the drawer holds exactly two numeric
money inputs; and that they are seeded from the typed backend facts (`0`, `200`,
`monthly`) rather than parsed from display strings.

## The backend card

```
status:  ready_to_run
actions: run_backtest, adjust_assumptions, cancel_confirmation

rows:
  strategy        | Strategy          | Recurring Buys
  assets          | Assets            | KO
  period          | Period            | January 2, 2020 - December 31, 2024
  starting_capital| Starting capital  | $0
  contribution    | Contribution      | $200 monthly

assumptions:
  $0 starting capital
  $200 monthly contribution
  Daily data
  No fees
  No slippage
  Benchmark: SPY
```

No cadence row exists to render. The card advertises
`edit_constraints.starting_capital` (floor `0`) and
`edit_constraints.contribution` with the five periods that fit the five-year
window; a three week window advertises only `daily`, `weekly`, `biweekly`.

## The two invariants

`tests/domain/test_dca_capital_semantics.py` (67 cases).

1. **Structural.** A guard walks every `.py` under `src/argus` and rejects any
   `a or b` or `a if … else b` that would take one capital role's value when the
   other is missing. Written against the whole tree, not the flagged line, so
   the shape cannot reappear in a file this lane never touched. On its first run
   it found two live cross-role ternaries in `runner.py` and `charts.py`; both
   now go through one owner, `symbol_allocation_capital`.
2. **Behavioural.** The cross product of three distinct seeds, three distinct
   contributions, and all five periods (45 combinations) asserts each role round
   trips as itself and that a recurring engine config carries no
   `starting_capital`, `recurring_contribution`, or `starting_principal` slot for
   either role to be read out of.

## The real-calendar proof

`tests/domain/test_dca_trading_day_rule.py` measures the non-trading-day rule
against the actual 2024 NYSE sessions (`tests/domain/nyse_calendar.py`: the ten
real closures and three real early closes, enumerated rather than derived).

The test is not vacuous. Run against a synthetic calendar-day fixture, the same
monthly plan buys on four days the exchange was shut:

```
contribution dates on a calendar-day fixture: 2024-01-01, 2024-02-01, 2024-03-01, ...
of those, days the exchange was CLOSED: 2024-01-01, 2024-06-01, 2024-09-01, 2024-12-01
```

Against the real session calendar, every contribution in every period lands on
an open session, January buys on the 2nd, and September buys on the 3rd because
the 1st was a Sunday and the 2nd was Labor Day.

The provider mode is pinned inside the module: coverage skips the calendar
entirely in synthetic mode, so inheriting the runner's mode would let these
assertions pass by never consulting a calendar at all.

## Three defects found while proving the lane

The first two were introduced here; the third was pre-existing and defeated a
founder requirement outright.

1. `edit_constraints` advertised a `$0.01` contribution minimum the plan never
   had, a second and stricter rule that would have refused a run the engine
   accepts.
2. The backend emitted a `fractional_shares` receipt key the frontend's frozen
   vocabulary had never heard of, so the fact would have reached a shared page
   and been dropped. The repo's own closed-set test caught it.
3. Narrowing a window below its contribution period is required to refuse
   immediately and name the rule. It said "One part of the draft is not
   executable in the current backtest engine" instead, because
   `_validation_error_code` matched five hard-coded strings and called
   everything else `missing_rule_group`. Every code this lane added degraded the
   same way. The code is now read from the structured error pydantic already
   carries:

   ```
   narrow to 3 weeks with monthly selected      -> contribution_period_exceeds_window
   ask for quarterly in a 3-week window         -> contribution_period_exceeds_window
   switch to quarterly in a 12-month window     -> applied
   ```

## Test results at this head

- Backend, hermetic (`ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture`,
  provider keys blanked): **5082 passed, 489 skipped, 2 failed**. Both failures
  are `tests/memory/test_mem0_configuration.py`, `ModuleNotFoundError: No module
  named 'mem0'`: the package is not installed in this worktree's venv, and
  `git diff 3602ca16..HEAD -- tests/memory src/argus/api/personalization_memory_index.py src/argus/memory`
  is empty, so those paths are byte-identical to the base. CI installs the
  package and passes them.
- Frontend unit: **1482 passed, 0 failed** across 144 files.
- Frontend typecheck: clean. Lint: 0 errors (8 pre-existing warnings).
- `next build`: succeeded.
- Browser: **4 passed** (en/es-419 × phone/desktop).
- New tests in this lane: **68** in `test_dca_capital_semantics.py`, **10** in
  `test_dca_trading_day_rule.py`, plus the end-to-end seeded-plan pair in
  `test_engine_launch.py`.
- `ruff check .`: passed.
- `scripts/check_modularity_budget.py`: no violations.
