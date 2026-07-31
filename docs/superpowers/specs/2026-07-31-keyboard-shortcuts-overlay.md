# Keyboard Shortcuts Overlay + Quick-Jump — scope note

Light-touch note, not a full argus-lane-delivery spec. Amended 2026-07-31:
grew from a small reference overlay into a keyboard quick-navigation
system with a reusable numbered quick-jump primitive, founder-directed.
Named explicitly here so the size increase is a decision, not drift.

## Locked decisions — overlay core (original scope)

1. Trigger: `⌘/` on Mac, `Ctrl+/` on Windows/Linux, plus a visible menu entry
   under Help/profile menu for discoverability. No bare-modifier trigger
   (bare Cmd or Ctrl alone) — conflicts with platform conventions.
2. `⌘K`/`Ctrl+K` for Omnisearch is untouched — this feature does not change
   that binding or its behavior in any way.
3. One central shortcut registry is the single source of truth, powering
   both the real key handlers and the overlay's displayed list. This
   prevents the overlay from documenting a shortcut that doesn't actually
   work, or missing one that does.
4. The overlay is invoked, not a persistently docked panel — opens on
   trigger, dismisses on Escape/click-away/re-trigger. Nothing sits on
   screen when not actively summoned.
5. No user-remapping system in v1.
6. No edits to Omnisearch behavior or any existing typed action's semantics.

## Locked decisions — expanded action set (2026-07-31 amendment)

7. New actions to register, each needing its own binding: **new chat**,
   **open recents**, **delete the focused chat**, **rename the focused
   chat**, **open the sidebar and expand Recents**, **open Settings**,
   **pin/unpin the focused chat** (one toggle action, not two separate
   binds).
8. **"Open recents" vs. "open sidebar and expand Recents" — unresolved,
   ask the founder directly rather than assume they're the same action or
   guess a distinction.** Do not silently merge them or silently treat
   them as different without confirming.
9. **Delete requires confirmation, always.** If a confirm step already
   exists on the mouse-driven delete flow, the keyboard trigger must go
   through that same flow, never an instant unconfirmed delete. If no
   confirm step exists anywhere today, stop and report — whether delete
   should have confirmation at all is a product decision, not
   implementation detail.
10. **Confirm before assuming rename, delete, and pin/unpin already exist
    as actions somewhere in the UI** (hover icon, context menu). Argus's
    release-integrity contract already names a "pinned conversation
    group" as an existing concept, so pin/unpin is likely wiring a
    keyboard trigger to something that already exists — verify, don't
    assume, same as rename/delete. If any of these three don't exist as
    an action at all yet, that's new conversation-management UI, a bigger
    scope than "add a shortcut" — stop and report rather than building it
    silently.
11. **Numbered quick-jump primitive.** While Cmd is held over a visible
    list (Recents when expanded, Settings including nested subsettings),
    each visible item shows a numbered badge (1-9); pressing the number
    jumps to/opens that item. Scope to only the currently *visible* items
    — Recents already has bounded pagination (#245/#302); do not number
    anything behind "Load older." For Settings' nested subsettings, no
    special nested-numbering logic is needed: number whatever's visible
    at whatever depth you're currently at — holding Cmd at the top level
    numbers top-level categories, drilling into one and holding Cmd again
    numbers that category's own subitems.
    - **On Recents specifically: pinned chats get numbered first**,
      regardless of interleaved recency — all pinned chats take 1, 2, 3…
      before any unpinned recent chat gets a number. Not strict visual
      top-to-bottom order if that would ever put an unpinned chat ahead of
      a pinned one; pin status determines number priority, not just
      position. Depends on confirming decision 10's existing pinned-group
      mechanics before implementing the numbering on top of it.
12. **Build the quick-jump behavior once, as a shared primitive both
    Recents and Settings consume — not two independently-built copies.**
    This is the same lesson as the failure-class-visual-consistency lane:
    two hand-built implementations of the same concept drift apart over
    time. Build one, applied in two places.
13. The numbered overlay must coexist cleanly with whatever hover actions
    already exist on Recents rows — don't let the badge visually fight
    with or disable existing hover affordances.
14. Exact key chords for every new action (new chat, open recents/expand
    sidebar, delete, rename, open Settings, pin/unpin) are **not locked
    here.** Propose candidates, check them against the existing bindings
    (`⌘K`, `⌘/`) and common browser/OS-reserved combos, report the
    proposed set before finalizing. A silent chord collision is worse
    than one more confirmation round.

## Left to the agent's taste

- Exact overlay visual design, layout, animation.
- Grouping/ordering of shortcuts within the overlay.
- Visual styling of the numbered quick-jump badges (bounded by: must be
  legible, must not obscure the item's own label/hover controls).

## Stop and report if

- Achieving the original overlay requires changing the existing `⌘K`
  binding or any typed action's behavior.
- A genuine remapping/customization need surfaces — out of v1 scope.
- Rename, delete, or pin/unpin don't already exist as actions anywhere in
  the UI.
- Delete has no existing confirmation step anywhere.
- Any proposed key chord collides with an existing binding or a common
  browser/OS reserved combo.

## Where it stops

One PR against `codex/private-alpha-next` (or a small stack, if the
expanded scope warrants splitting the overlay core from the quick-jump
primitive — agent's call, name the shape before starting). Gates:
EN/es-419, hermetic frontend suite, screenshots of the quick-jump overlay
on both Recents and nested Settings, no backend/schema changes expected
(flag if one turns out to be needed).
