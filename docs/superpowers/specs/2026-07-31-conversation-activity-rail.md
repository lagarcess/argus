# Conversation Activity Rail (the "minimap") — scope note

Researched, not guessed: OpenAI's Codex desktop app has a UI element
informally called an "activity rail" (confirmed via a live GitHub issue on
openai/codex, #30275) — a vertical dashed strip alongside a long agent
session, with hover-triggered preview popovers, letting you scan a long
timeline without scrolling and jump to a point of interest. That's what's
visible in the shared screenshot.

That same GitHub issue is real users complaining the hover trigger sits in
their normal cursor path between the sidebar and main panel and fires
unwantedly. Worth designing around explicitly, not rediscovering the hard
way.

Argus analog: a compact vertical strip alongside a long chat transcript,
with ticks for significant turns (backtest completed, decision saved,
error/recovery), hover shows a compact preview, click scrolls the
transcript to that turn.

## Locked decisions

1. This is a **navigation/preview aid over the current conversation's own
   turn history only.** Clicking a tick scrolls to that turn in the same
   transcript. It does not open a new panel, does not let you edit a
   decision, does not browse other conversations' runs — that is
   Omnisearch/#309's job. This must not duplicate or compete with the
   dossier-history surface #309 is actively building.
2. **Ticks represent a small, fixed set of turn kinds — but that exact set
   is not locked here, and should not be invented.** Argus already has an
   established typed-outcome taxonomy from #304 (Quick take, Explain
   result, Try next, recoverable/retryable failure) plus the decision-
   state concept from #253/#309. Before implementing, propose a tick
   taxonomy grounded in what already exists — do not build against an
   arbitrary guessed list, and do not turn this into a place for freeform
   annotation or a brand-new taxonomy invented for this feature alone.
   Report the proposed set before finalizing if it's not obvious which of
   the existing typed outcomes deserve a tick versus being too frequent/
   minor for a coarse-grained rail.
3. Hover-preview must not fire on incidental contact — this is the exact
   bug Codex's own users are hitting (instant-fire on first touch, sitting
   in the normal path between two frequently-used regions). Two founder-
   directed mitigations, both required, not alternatives:
   - **Proximity/dwell gating, not instant hover-fire.** The rail "wakes
     up" as the cursor nears (a magnetic-reveal ramp, roughly a half-inch
     threshold) rather than triggering the instant it's touched. Exact
     distance/timing is a tuning detail for the agent, not a hard number.
   - **Right-edge placement**, since the left edge is where the actual
     Codex bug happens (between sidebar and main panel). Before locking
     this: check whether Argus's chat layout already uses right-side real
     estate for something else. Omnisearch's own preview pane has
     historically lived on the right (`ChatCommandPalette.tsx`'s right
     pane — chips → title → preview card). Confirm there's no collision
     with that existing surface before assuming the right edge is free;
     if it's occupied, report back rather than picking a different edge
     unilaterally.
4. No new durable model. Ticks are derived from existing turn/message data
   at render time, not a new backend table or stored annotation.
5. Zero LLM/provider calls to generate previews — preview content comes
   from already-existing structured turn data (result-card facts, decision
   state), same zero-LLM discipline used throughout Omnisearch/#309/#310.
6. **Tick taxonomy: ship the 3-kind set** — Result turn (the
   `strategy_result` message carrying Quick take), Decision saved (a
   result turn whose artifact has a decision-state — supersedes kind 1
   for that turn, not additive), Needed attention (typed
   recoverable/retryable failure). Try next and Explain result are
   deliberately excluded — both are attached to an existing result turn
   rather than being a distinct turn, and ticking them too would
   double-mark the same position in the conversation. One tick per
   distinct turn, not one per typed outcome.
7. **Visual quality bar, added after the avatar lane landed generic on
   the same kind of undirected taste call — don't repeat it here.**
   - Default state should read as ambient/quiet, not a bold attention-
     grabbing bar sitting on screen at all times — subtle presence at
     rest, richer only on proximity/interaction (the same restraint
     VS Code's own minimap uses).
   - The popover, when triggered, needs real visual hierarchy — not just
     dumped text. A per-kind visual signal (color/icon) distinguishing
     Result / Decision saved / Needed attention at a glance.
   - **"Needed attention" reuses whatever shared amber/failure treatment
     the failure-class-visual-consistency lane produces — do not invent
     an independent color/style for it.** That lane exists specifically
     to stop independently-built failure treatments from drifting apart;
     inventing a fourth one here would recreate the exact problem it's
     fixing. If that lane's shared component isn't ready yet, use a
     clearly-marked placeholder and flag it for a follow-up swap — don't
     finalize a bespoke treatment now that then needs reconciling later.
   - Motion on reveal should be a single restrained transition, not
     multiple stacked effects — matches Argus's existing zero-flash
     discipline elsewhere in the UI.
   - Render and screenshot before finalizing — this is a visual bar,
     verify it visually.

## Left to the agent's taste

- Visual density/spacing of ticks, fixed-width rail vs. proportional
  minimap, exact popover layout within the hierarchy above.
- Whether it's always present or only appears past some turn-count
  threshold (suggested default: only worth showing on longer
  conversations, not a hard lock).
- Naming — "activity rail" is Codex's internal name; Argus should probably
  have its own (e.g. "conversation rail," "turn map") — agent's call.

## Stop and report if

- It would require a new durable per-turn tag/importance model.
- It would require any LLM call to summarize a turn for the preview.
- It starts overlapping #309's surface — e.g. letting a user change a
  decision from the rail itself.

## Where it stops

One PR against `codex/private-alpha-next`. EN/es-419, hermetic frontend
suite, zero-provider-call proof, screenshot evidence given this is a new
visible UI surface.
