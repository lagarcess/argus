# Confirmation card inline edit (capital + dates) — scope note

## Why

The confirmation card's edit runtime today is conversational turns or
action chips (Change dates, Change asset, Adjust assumptions). A user
requested: let capital/investment amount be edited by clicking the value
directly on the card and typing a new number in place, rather than always
going through chat. Discussed at length before locking scope, because the
naive version of this idea ("make every parameter clickable") is a real
risk — it drifts Argus from chat-first toward a parameter-form/spreadsheet
UI, which `docs/PRODUCT.md` explicitly names as an anti-pattern
("Spreadsheet Software... parameter overload"; "Simplicity Wins... avoid
complex dashboards, knobs, and enterprise UX").

Resolved by drawing a narrow, principled line rather than a blanket
feature, and by putting the whole thing behind flags — the founder wants
this reversible in case it looks bad in practice, unnecessary once
conversational parameter resolution improves, or worth A/B testing later.

## Locked decisions

1. **In scope: capital/investment amount only, as true inline
   click-to-edit.** Click the value on the card, type a new number, it
   commits in place. This is the one field where inline editing clearly
   passes PRODUCT.md's own decision filter ("does this make it easier for
   a normal person to continue exploring?") — it's a pure scalar with no
   cross-field validation, and typing a number inline isn't slower or
   less expressive than saying it in chat.
2. **Dates: chip-triggered popover/calendar anchored at the clicked
   field, not bare inline text and not a full drawer.** A drawer is
   reserved for grouped multi-field editing (matches the existing "Adjust
   assumptions" chip's shape); a single date is a smaller edit than that.
   The popover is a shortcut for exact-date cases only — it does not
   replace the conversational date language (year-to-date, rolling
   windows, "since the 2020 crash," fractional periods per the
   [fractional-month note](2026-08-01-fractional-month-date-resolution.md)),
   which stays strictly more expressive than any date-picker and remains
   fully available.
3. **Explicitly out of scope, not a future default: symbols, benchmark,
   strategy type, and any field with cross-field validation.** These stay
   chip + conversational only. Do not treat this note as opening the door
   to inline-editing everything — extending inline edit to another field
   requires its own explicit decision, re-run through the same reasoning
   (does removing the chip/conversational step lose real
   validation/interpretation value for that specific field), not an
   assumed extension of this pattern.
4. **Both surfaces route through the exact same typed edit-operation /
   deterministic-applier path the conversational runtime already uses.**
   No second, parallel mutation path. An inline capital edit and a typed
   "change capital to $15,000" chat turn must produce the identical
   operation.
5. **Each inline edit commits as its own separate operation immediately —
   never batched with another pending inline edit.** This belongs to the
   same ownership as the G-05 compound-edit bug (confirmation-card edits
   only partially applying a two-field request); it is not a new
   independent finding, and its fix must land with that bug's owner, not
   as a standalone item here.
6. **Validation (min/max/unsupported) reuses the exact limit messages
   already enforced elsewhere** (one asset class per run, max 5 symbols,
   long-only, benchmark must match asset class, etc.) — no new,
   inline-only copy invented for the same rules.
7. **Scope boundary: inline edit applies only to the pre-Run draft
   confirmation state.** Once a Run produces a real result/artifact,
   this mechanism no longer applies — further changes go through
   Retest/refine. This is deliberate, not an oversight: there is no
   canonical version to fork before a Run exists, so this doesn't
   collide with P2's future linked-IdeaVersion concept (A1b), which is
   about versioning *completed* ideas. Do not extend inline edit to a
   completed result's card without a fresh decision once A1b lands.
8. **No new evidence/audit record is required for inline edits**, given
   decision 7 — they're pre-canonical draft state, not a durable artifact
   yet. The Run action is still what captures final values into the real
   canonical record. Flag if this reasoning turns out to be wrong once
   implementing against the actual draft/artifact boundary in code.
9. **Guest parity is required.** No guest-degraded version of this — same
   behavior for guest and signed-in, consistent with not repeating the
   second-class-guest pattern already found in the 2026-08-01 checkpoint
   evidence doc.
10. **Real touch/tap equivalent required for mobile**, not a
    desktop-hover-only assumption.

## Feature flags (required, not optional)

1. **Capital inline-edit and the dates popover are gated by separate
   flags**, not one bundled flag — they should be independently
   rollback-able and independently A/B-testable, since they're different
   UI surfaces with different risk profiles (capital is low-risk/simple;
   the dates popover has more surface area to get wrong).
2. Default state (on/off at launch) is left to the agent's judgment,
   bounded by: both must be a clean, instant kill switch with no data
   migration or cleanup required to disable — this is presentation/
   interaction surface only, not a durable schema change.
3. Naming convention: follow the existing `NEXT_PUBLIC_*`-prefixed
   frontend-flag pattern already used for comparable presentation gates
   (e.g. `NEXT_PUBLIC_COLLECTIONS_ENABLED`, `NEXT_PUBLIC_STRATEGIES_ENABLED`).
   Exact names left to the agent.

## Left to the agent's taste

- Exact inline-edit interaction details (click target size, focus/blur
  commit behavior, live vs. on-blur validation).
- Exact popover layout, size, and animation for dates.
- Default flag state at launch.

## Stop and report if

- The typed edit-operation path can't cleanly accept an operation
  originating from a UI click rather than an interpreted chat turn
  without deeper runtime changes than this note anticipates.
- The pre-Run/post-Run draft boundary (decision 7) doesn't cleanly exist
  in the current data model — report rather than guessing where the line
  actually falls.

## Where it stops

One PR (or a small stack, if capital and dates warrant splitting) against
`codex/private-alpha-next`. Gates: EN/es-419, hermetic frontend suite,
evidence that both flags independently disable their surface with no
residual effect, evidence that inline edits and chat-driven edits produce
identical operations, and confirmation that guest and signed-in behave
identically.
