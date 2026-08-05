# Omnisearch shortcut legend — scope note

Founder decision from the S-13 finding in
[`docs/reports/2026-08-01-current-checkpoint-experience-feedback.md`](../../reports/2026-08-01-current-checkpoint-experience-feedback.md)
(locked evidence, do not edit). This note covers only the shortcut-legend
half of S-13. The non-backtest conversation preview sizing/truncation
half of S-13 is a separate concern and not addressed here.

## Why

The evidence doc's own "Enter opens the match · ⌘/Ctrl+Enter opens where
you left off" footnote isn't shown consistently, and the doc left open
whether a shortcut legend should exist at all, offering two options if so:
a contextual legend (hidden until a modifier is held) or a persistent
interactive legend (always visible, clickable). Founder-locked: **Option
A, the contextual legend.**

## Locked decisions

1. **The legend is hidden by default** and reveals only while Cmd/Ctrl is
   held and the relevant action region is hovered — not a persistent
   fixture in the footer.
2. **This matches Argus's own established restraint pattern, not a new
   one.** The conversation-activity-rail spec already locked the identical
   principle for its own surface: "ambient/quiet at rest, richer only on
   proximity/interaction." Apply the same restraint here rather than
   inventing a different visual language for Omnisearch specifically.
3. **Remove the current inconsistent footnote entirely** ("Enter opens the
   match · ⌘/Ctrl+Enter opens where you left off") — do not display both
   the old sentence and the new contextual legend at once.
4. **Add shortcut hints for actions already exposed on hover** — Rename,
   Archive, Delete — alongside existing Enter navigation, using the
   existing compact pattern `Action [symbol or shortcut]` (e.g. `Go [↵]`,
   `Rename [shortcut]`), consistent with established shortcut visuals
   elsewhere in the app.
5. **Collapse stays persistent and is excluded from the hover-triggered
   hide/reveal** — it controls the Omnisearch surface itself, not a
   per-row action.
6. **Footer guidance must read the same regardless of whether the
   selected conversation has a backtest artifact** — no separate legend
   variant for backtest vs. non-backtest previews.
7. **Result-number shortcuts, if built in the same pass**: while Cmd/Ctrl
   is held, enumerate visible results top-to-bottom as `1`–`9`; replace
   each row's date with its number hint for the duration the modifier is
   held, restoring the date on release. Command hints must track current
   visible ordering and never activate hidden/filtered rows.
8. **Every displayed shortcut must work through both its keyboard path and
   any displayed click target** — the legend must never advertise an
   action that doesn't actually exist yet (the evidence doc's own
   PRODUCT.md challenge: reject anything that "advertises actions that are
   not actually implemented").
9. Keyboard hints must remain discoverable, localized where necessary, and
   platform-correct on macOS vs. Windows/Linux.

## Left to the agent's taste

- Exact placement/spacing within the footer region (left-edge start,
  right-side weighted, per the evidence doc's own layout note).
- Exact reveal/hide transition timing — bounded by: a single restrained
  transition, consistent with Argus's zero-flash discipline elsewhere.
- Whether Rename/Archive/Delete already have real keyboard bindings to
  expose, or need new ones — confirm before assuming; don't build new
  keybinding behavior beyond what the legend needs to describe truthfully.

## Stop and report if

- Rename, Archive, or Delete turn out to have no existing keyboard path at
  all — that's new keybinding behavior, a bigger scope than "add a
  legend for what already works." Report before building it.
- Verifying against `docs/PRODUCT.md`'s decision filter (does this reduce
  time-to-act without adding dashboard-like density?) suggests no legend
  should exist at all — report that finding rather than building Option A
  anyway; this note assumes the answer is yes, some legend belongs here,
  but that assumption should be confirmed against the actual rendered
  result, not just this note's text.

## Where it stops

One PR against `codex/private-alpha-next`. Gates: EN/es-419, hermetic
frontend suite, screenshot evidence of the legend both hidden (at rest)
and revealed (modifier held), and confirmation that every advertised
shortcut actually executes its described action.
