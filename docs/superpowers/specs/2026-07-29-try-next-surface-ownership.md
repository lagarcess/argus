# Try Next Surface Ownership — locked product decisions for #249

Status: **LOCKED by founder, 2026-07-29.** This spec records the product
decisions for issue #249 (result-surface and recovery-presentation
ownership) agreed in the founder conversation of the same date. It amends
nothing in #249's no-touch list and inherits its acceptance criteria;
where this spec is more specific, this spec governs.

Serialization: this lane runs first, #253 (Omnisearch recall) after it.
The #244 exposure-vehicle design stays parked until both land.

## 1. One surface: the stacked rows ARE Try next

Try next and the stacked next-move rows were two names for one intention.
The rows underdeliver against the full Try next vision; Try next has no
surface of its own. Decision: **unify.**

- The stacked next-move rows become the one Try next surface: one
  identity, one owner, localized "Try next" chrome with a correct
  accessible section name.
- There is no second suggestion affordance anywhere on the result
  surface, and — per #249's standing no-touch — no result-card CTA.
- The long-term vision this surface must be shaped for: one dynamic
  follow-up point that evolves as Argus gains capabilities (comparisons,
  memory, personalization) and cleverly offers the highest-value next
  step. The surface contract below is designed so those arrive as new
  inputs, never as another surface migration.

## 2. Three standing constraints on the unified surface

1. **A union of typed rows, never a blended generator.** Every row kind
   carries its own grounding contract (experiment rows:
   supported-template validation; discovery rows: resolver validation and
   citations; future kinds: their own). No generator output may inherit
   the surface's credibility without its kind's grounding.
2. **Graceful degradation.** Typed deterministic rows render even when
   any smarter layer fails. The surface degrades to "still useful,"
   never to empty and never to blocking the result.
3. **Goal-bounded ranking language.** Rows are selected for continuation
   value toward the user's goal, bounded to supported actions.
   Engagement is earned through usefulness; nothing may read as a
   performance promise or investment recommendation. Education-only
   stays bright.

## 3. Staged ranking doctrine (founder-ratified verbatim)

The staging below was pulled from the decision conversation and ratified
as written. It is the governing doctrine for how this surface gets
smarter:

> Then two upgrade paths, in order:
>
> **Evidence-based ordering** from the telemetry above — statistics, not
> models.
>
> **Eventually, an LLM selector — with one hard rule: the model may
> *choose and phrase*, never *mint*.** It picks from pre-validated
> candidate rows (constrained to their ids, same structured-output
> pattern the interpreter already uses) and can sharpen the wording; the
> validated set is composed before it ever runs. That's the safe form of
> "smart": the intelligence ranks, the type system decides what's
> offerable. When memory lands, that selector is where user context
> plugs in — the contract doesn't change, its inputs do.

Concretely, three stages, strictly in order:

- **Stage 0 — ships with #249:** deterministic typed selection policy,
  conditioned on the typed result state. Testable, free, language-
  agnostic. No LLM in the render path.
- **Stage 1 — later lane:** ordering informed by row-level telemetry
  (statistics over impressions/acceptances). Still no model.
- **Stage 2 — later lane:** an LLM selector over pre-validated candidate
  rows under the choose-and-phrase-never-mint rule. Memory and
  personalization plug in here as selector inputs when they exist.

## 4. The frontier bar (all Stage-0 obligations except where noted)

1. **Result-aware selection.** Rows read like they saw the result: a
   deep drawdown surfaces the risk-rule experiment, a benchmark loss
   surfaces the comparison twist, a strong baseline surfaces discovery.
   Conditioned on the typed result payload only.
2. **Guaranteed-runnable rows.** A row is offered only if its action
   would pass the same validation the card enforces — supported
   template, resolver, and the bars-coverage probe for anything
   comparison-shaped (#303 machinery). Contract: if offered, it runs.
3. **Non-repetition and restraint.** Never re-offer what this
   conversation already ran or ignored; cap the row count; when nothing
   valuable remains, show fewer rows or none. No padding.
4. **Latency discipline.** The result paints first, always. Rows never
   block it and require no LLM call to render.
5. **A typed "why" on each row.** Each row carries its reason as data
   (e.g. the drawdown figure, the source count). May render as a small
   caption; must exist as typed metadata either way, so future ranking
   explanations stay honest.
6. **Measurement loop.** Row-level impression and acceptance telemetry
   through the existing observability spine, keyed by row kind and
   position. This is what Stage 1 consumes.

## 5. Explain cleanup ships in the same slice

"Useful next check" material inside Explain result existed because Try
next was too deep in the funnel. The unified rows are eager — rendered
under the result, no click — so the workaround retires. Explain becomes
pure grounded comprehension.

Sequencing rule: the Explain cleanup and rows-as-Try-next land in the
same slice. No release may have a suggestion gap.

## 6. Recovery presentation (one taste decision deliberately open)

Locked: generic recoverable failure never renders under Quick take, Try
next, Explain, or What happened chrome; compact-adjacent treatment when
the owning action identity exists; visibly-a-failure treatment (never a
normal assistant answer) when it does not.

Open until the founder sees both states side by side during the lane:
the exact visual language of the distinct-failure treatment (tone, icon,
retry placement). The lane presents both before locking.

## 7. Gates inherited and updated

- **Validation before implementation:** the lane's first act is an
  exact-head re-check of the three verified shapes (recovery chrome
  emission, Explain "Useful next check" composition, malformed option
  rendering) at the current integration tip, recorded on #249.
- **#244 criterion is now active:** typed discovery outcomes exist on
  integration; the rows must preserve them rather than replace them with
  generic suggestions. Compatibility work, not discovery ownership.
- Stop for a contract gate if implementation requires any new public
  action, option, or recovery shape (#249's standing rule).

## 8. Founder lightbulb — prebaked rows (added mid-lane, 2026-07-29)

Captured verbatim-in-substance from the founder during live QA; this is
the next evolution of Stage 0, to build in this lane or its immediate
follow-up:

1. **Prebaked concrete rows.** The why-suffix pattern on row one sparked
   it: "Test the same setup on a similar asset" should carry its own
   affordance — a concrete, pre-resolved similar asset appended to the
   row (e.g. "· MSFT"). Tapping it asks nothing: Argus answers with the
   next **confirmation card directly**, because the row was prebaked
   through the full grounding chain before being offered — asset
   resolved in the catalog, runnable for the family, bars-coverage
   verified (#303 probe). "Is that our vision being realized?" — yes:
   this is guaranteed-runnable made literal.
2. **Spacing:** TRY NEXT needs a little more breathing room from the
   Quick take block.
3. **Swap the RSI row for DCA.** The RSI-threshold row is deterministic
   filler; replace it with the more common next experiment — recurrent
   buys / DCA — phrased smoothly, and **prebaked with the previous
   run's compatible assumptions and parameters** (same asset, dates,
   capital; only the strategy changes), so the tap again lands on a
   ready confirmation card.

Implementation shape: extend the sidecar row contract with an optional
prebaked launch payload (asset/params filled from the completed run +
deterministic peer selection validated through resolver + coverage
probe); a prebaked row's tap submits that payload into the normal
confirmation lifecycle instead of a conversational ask. Rows without a
prebake keep the conversational path. No new public action type without
the contract gate — reuse the existing confirmation/launch contract.
