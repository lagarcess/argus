# Fractional-month date resolution — scope note

Founder decision from the S-10 finding in
[`docs/reports/2026-08-01-current-checkpoint-experience-feedback.md`](../../reports/2026-08-01-current-checkpoint-experience-feedback.md)
(locked evidence, do not edit). Requesting "the last 8.5 months" on
2026-08-01 resolved to December 1, 2025 through July 31, 2026 — the half
month was silently dropped. A proportional interpretation would have begun
around mid-November 2025.

## Why

Argus's own positioning is built on handling messy, natural language
without asking users to be precise ("Users should only need curiosity" —
PRODUCT.md). Asking "did you mean November or December?" every time
someone says "6 and a half weeks" or "8.5 months" adds exactly the kind of
friction the product is supposed to avoid. Founder-locked: support
fractional-period requests deterministically, not by asking for
clarification.

## Locked decisions

1. **Fractional-month (and other fractional-period) requests resolve
   deterministically, not via a clarification turn.** No new prompt asking
   the user to restate the period.
2. **Define an exact calendar rule, not model approximation.** A
   fractional month must resolve by real day-count, not by rounding to the
   nearest whole month. `N.5 months` back from an anchor date must land
   proportionally between the whole-month and next-whole-month boundaries
   — matching the doc's own math check (8.5 months back from 2026-08-01
   lands near mid-November 2025, not December 1).
3. **Check the existing `rolling_window` mechanism first.** The interpreter
   already supports `rolling_window` with `count`, `unit`, and
   `anchor=today` (hardened in `0e81810b`, `feat(edit-contract): harden
   planner prompt`). Determine whether this already accepts fractional
   `count` values, or whether the fractional component is being dropped
   downstream of that classification (interpreter, deterministic date
   resolver, or later coverage normalization, per the evidence doc's own
   "Unknowns to investigate later"). Fix at the layer that's actually
   dropping it — do not build a second, parallel date-resolution path if
   the existing one just needs to stop truncating.
4. **Ordinary trading-session/calendar alignment stays quiet, as already
   established** (see the already-closed G-04 finding in the same evidence
   doc). This decision is only about the fractional-period math itself,
   not about weekend/holiday normalization layered on top of it.
5. Apply the same deterministic rule regardless of unit (weeks, months,
   years) if the codebase already generalizes `rolling_window` across
   units — don't special-case months alone if the fix naturally covers the
   general case.

## Left to the agent's taste

- Exact day-count formula (e.g. average month length vs. exact calendar
  subtraction) — bounded by: it must produce a result consistent with the
  evidence doc's own mid-November check for the 8.5-month case.
- Whether the fix is a one-line change to stop truncating, or requires
  passing the fractional component through an intermediate typed field
  that currently only carries whole numbers.

## Stop and report if

- The fractional component is being dropped in a shared/protected runtime
  file that requires touching more than the date-resolution path itself.
- `rolling_window` turns out not to be the right mechanism at all, and a
  genuinely new date-request shape is needed — report before building one.

## Where it stops

One PR against `codex/private-alpha-next`. Gates: EN/es-419, hermetic
suite, a focused regression test asserting the exact resolved window for
at least one fractional-month and one fractional-week case, and evidence
that ordinary whole-period requests are unaffected.
