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
2. **The existing Retest token chip remains identity-only.** When Retest is
   available, the confirmation discloses the original-to-updated period and
   natural duration. The dossier owns whether Retest can be started at all.
3. **Every unrelated owned assumption must survive the transformation
   unchanged** — asset, capital, benchmark, execution costs, timeframe.
   Only the date window moves.
4. **The dossier computes one of three server-owned states before click.**
   The client renders this typed truth and never recomputes provider limits:
   - `new_data_available`: enabled normal Retest. It enters the existing
     confirmation and job-polling path; no exact delta is promised.
   - `no_new_data`: disabled informational action. The dossier says that the
     run is already current before click. It emits no chat turn, simulation
     request, job, or backtest row. The old confirmation-card same-period
     acknowledgment is removed completely.
   - `cant_do_it`: carries one canonical violation code. For
     `provider_history_start_unavailable` and `kraken_ohlc_window_exceeded`,
     the server also carries one `clamp_start` repair with exact start/end
     values. That guided action is enabled and admission applies the same
     repair before preflight. `provider_timeframe_unavailable` has no repair
     and renders as a disabled dead end.
5. **Canonical window validation is shared.** Dossier eligibility and Retest
   admission both use `market_data_window_violation`; a proposed clamp is
   revalidated through `validate_market_data_window` before it is offered.
   The repair preserves the provider-effective end and changes only start.
6. **No new frontend state machine.** No modal, toast, checkbox, or second
   confirmation is added. Post-click queued/running/completed status remains
   owned by the existing chat job-polling flow.

## Localized copy

All dossier state and repair copy is present in English and es-419. Provider
names stay internal. Dates come from the server repair and are formatted by the
client locale; the client does not alter them.

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

One PR against `codex/private-alpha-next`. Gates: EN/es-419, hermetic backend
and frontend suites, the owned `chat-action-recovery` browser spec, focused
proof for all three dossier states and both repair codes, zero same-period
simulation mutations, and the unchanged normal confirmation/job path.
