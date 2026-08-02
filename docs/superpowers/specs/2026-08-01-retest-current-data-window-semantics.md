# Retest "current data" window semantics — scope note

Founder decision from the S-12 finding in
[`docs/reports/2026-08-01-current-checkpoint-experience-feedback.md`](../../reports/2026-08-01-current-checkpoint-experience-feedback.md)
(locked evidence, do not edit). Retest with current data reached a valid
confirmation but the subsequent Run request failed to recover — separate
from this note's scope, which is only the *meaning* of "current data" and
the resulting same-period edge case. The evidence doc's own S-12 Run-recovery
failure is a distinct bug, not addressed here.

## Why

The evidence doc left the meaning of "current data" explicitly undecided
between three options: shifted window (preserve duration, move both
endpoints forward), extended window (keep the original start, extend only
the end), or explicit user choice. Founder-locked: **extended window** —
"bring my results up to date," not "run an equivalent but different
period." This is the smaller, more honest change to what the user already
reviewed once, and matches what the feature's own name implies.

## Locked decisions

1. **"Current data" means extended window: preserve the original start
   date, advance only the end date to the latest available data.** Not
   shifted window. Not offered as an explicit user choice in this pass —
   revisit only if real usage later shows people want the shifted-window
   behavior too (don't build the second interpretation ahead of that
   signal).
2. **The chip and confirmation must disclose both periods clearly**,
   per the evidence doc's own "Required truth regardless of the decision":
   show the transformation, e.g. `<original period> → <updated period>`,
   and describe duration naturally rather than only as an exact day count
   (candidate language: "roughly two years," "~2 years" — exact wording
   left to the agent, bounded by: clarity over false precision).
3. **Every unrelated owned assumption must survive the transformation
   unchanged** — asset, capital, benchmark, execution costs, timeframe.
   Only the date window moves.
4. **Same-period edge case: when the extended end date equals the
   original run's date (no new data exists since the original run), don't
   let Run silently consume a simulation on a result guaranteed identical
   to one the user already has.** Founder-delegated design decision,
   locked as follows:
   - **Enhance the existing Ready-to-run confirmation checkpoint — do not
     add a new modal, popup, or toast component.** Retest already produces
     a confirmation card before Run; that's the existing guardrail. Adding
     a second, separate interruption on top of it violates the roadmap's
     own guardrail-ratchet principle ("do not add speculative strictness
     that blocks the Golden Path" beyond what's needed).
   - When the transformation is a no-op (updated period equals the
     original), the confirmation card must explicitly disclose this —
     e.g. "No new data since your original run" — not just show two
     identical dates and rely on the user noticing.
   - **The Run action itself must require an explicit acknowledgment in
     this one case**, not just be clickable as normal. Change its copy/
     framing (e.g. "Run anyway — no new data since original") so the user
     can't consume a simulation on an accidental duplicate without
     noticing. This mirrors the existing precedent for consequential
     actions elsewhere in the product (Delete always requires
     confirmation) rather than inventing a new interaction pattern.
   - A passive toast is explicitly rejected for this case — it's easy to
     miss, and this consumes a real, rate-limited simulation allowance
     (PRODUCT.md's Usage allowance section), not a cosmetic action.

## Left to the agent's taste

- Exact card copy for the same-period disclosure and the modified Run
  button, in both EN/es-419.
- Whether "no new data" is detected by comparing resolved dates directly,
  or by checking against the data provider's actual latest-available-bar
  timestamp (bounded by: it must be correct when the provider's latest
  data lags behind "today," e.g. weekends/holidays/end-of-day settlement —
  don't compare against wall-clock date alone if that would misfire).

## Stop and report if

- Fixing the Run-recovery failure noted in the evidence doc (the
  "confirmation was updated, I will keep the current confirmation intact"
  response) turns out to be required to even reach this same-period case
  — that's a separate bug per the evidence doc; report rather than folding
  its fix silently into this note's scope.
- The confirmation-card component doesn't have a clean way to vary its
  Run-button copy conditionally without broader refactoring — report
  before doing more than this note's scope requires.

## Where it stops

One PR against `codex/private-alpha-next`. Gates: EN/es-419, hermetic
suite, a focused test for the extended-window transformation, a focused
test for the same-period edge case (confirms Run requires the
acknowledged variant and that a normal Run still consumes exactly one
simulation as before), and screenshot evidence of both the normal and
same-period confirmation cards.
