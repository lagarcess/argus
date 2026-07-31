# Keyboard Shortcuts Overlay — scope note

Light-touch note, not a full argus-lane-delivery spec. Low decision surface,
frontend-only, nothing durable — the agent should have real latitude on
execution taste within these boundaries.

## Locked decisions

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

## Left to the agent's taste

- Exact overlay visual design, layout, animation.
- Grouping/ordering of shortcuts within the overlay.

## Stop and report if

- Achieving this requires changing the existing `⌘K` binding or any typed
  action's behavior.
- A genuine remapping/customization need surfaces — that's out of v1 scope,
  not something to quietly add.

## Where it stops

One PR against `codex/private-alpha-next`. Standard gates: EN/es-419,
hermetic frontend suite, no backend/schema changes expected (flag if one
turns out to be needed).
