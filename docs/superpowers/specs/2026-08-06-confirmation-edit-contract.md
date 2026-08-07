# Confirmation Edit Contract

Draft 2026-08-06. Spec only, no implementation authorized. Founder review
pending.

Board item 2 on [`argus-active-roadmap.md`](../../specs/argus-active-roadmap.md).
Serial, after item 1. Absorbs #335, the #141 macro, and the #237 umbrella.

## 1. The problem

Argus asks the user to confirm before spending a simulation. That card is the
last honest checkpoint in the loop, and it is where trust is currently lost.

Observed in alpha testing 2026-08-06: a user tapped **change dates**, then
broadened the request mid-sentence to include other changes while Argus was
waiting on a single field. The turn resolved ambiguously.

The lesson is subtler than "too many buttons". A scoped entry point must accept
a broader edit gracefully rather than holding the user to the button they
pressed. People change their mind mid-sentence; that is normal conversation, not
user error.

The second failure is compound edits. "Change this and add that" can silently
drop half the request in any language. Silent partial application is worse than
refusal, because the user confirms a card that no longer matches what they
asked for.

## 2. Current state

Five action types exist in `src/argus/api/schemas.py` around line 817:
`run_backtest`, `change_dates`, `change_asset`, `adjust_assumptions`,
`cancel_confirmation`. They render in
`web/components/chat/StrategyConfirmationCard.tsx` around line 460.

Edit routing lives in
`src/argus/agent_runtime/stages/interpret_internal/`:

- `contextual_merge.py` merges the current turn against prior context and holds
  the preserve-or-override decisions, including field-level provenance. This is
  the most likely home of the silent-drop behavior.
- `confirmation_artifact_edits.py` applies a resolved edit to the strategy
  summary.
- `date_contract.py`, `asset_resolution.py`, and `pending_date_answer.py` own
  the scoped paths.

## 3. Locked decisions

### 3.1 Three actions

The end state is **Run backtest**, **Change/edit assumptions**, **Cancel**.

`change_dates` and `change_asset` are retired as buttons.
Change/edit assumptions becomes the only entry point to editing anything.

**This is gated on section 3.2 being true first.** The retired buttons are
deterministic entry points that tell Argus exactly which field is being edited.
Removing them routes every edit through the free-form path. Shipping the
consolidation before compound edits are reliable would remove the working
escape hatches and leave only the broken one, making the alpha failure more
common rather than less.

The mobile lane may restyle these buttons for narrow screens but must keep all
five until this gate passes.

### 3.2 Compound edits never drop silently

A single turn may change any number of parameters. Every requested change is
either applied, or explicitly surfaced as not applied with a reason. There is no
third outcome.

- Partial application without disclosure is a defect, not a degradation.
- This holds in English and es-419 equally.
- It holds whether the user arrived through a scoped entry point or the general
  one.

### 3.3 Scoped entry points accept broader edits

If a user opens a narrow path and then asks for more, Argus widens to serve the
whole request. It does not discard the extra, and it does not restart the turn.

This is the direct fix for the observed alpha failure and applies for as long as
the scoped buttons exist.

### 3.4 In-place editing for capital and dates

Capital and dates get direct editing that spends no turn. This is additive; the
conversational path remains fully supported and is never replaced.

| Surface | Entry point | Container |
| --- | --- | --- |
| Web | a small dedicated row on the confirmation card, in the shape of the existing "edit costs" row | inline drawer, in the spirit of how the profile monogram is edited |
| Mobile | same row | the sheet primitive from the mobile spec, roughly 40 percent height |

Both surfaces share one pattern. The mobile spec already reserves this height
so that lane does not invent a second primitive. See
[`2026-08-06-mobile-pwa-responsive-shell.md`](2026-08-06-mobile-pwa-responsive-shell.md)
section 3.

Direct edits are ordinary edits: they obey the same validation, the same
coverage and resolver gates, and the same disclosure rules as a conversational
edit. Nothing becomes runnable that would not have been runnable through chat.

### 3.5 Repair must not drop what the user already stated (#367)

`FocusedStrategyExtraction` intermittently loses an explicit 10 bps fee and 5
bps slippage. The same prompt usually passes; one exact-head run returned an
executable confirmation with both costs and `launch_execution_realism` missing.
Confirmed nondeterministic, verified at `76e32322` against baseline `6533377c`,
and present in the clean integration baseline too.

This is the same defect as section 3.2 wearing different clothes. A repair path
silently discarding a stated cost is a compound edit dropping half the request,
just triggered by internal repair rather than by the user's next sentence.

So it is in scope here, and it constrains the fix:

- **One edit contract owns preservation.** Repair paths are not permitted their
  own rules about what survives. If `FocusedStrategyExtraction` can discard a
  user-stated value, so can any future repair, and each one becomes a separate
  bug. Route repair through the same contract, or make the contract the thing
  repair consults.
- **Silent loss is the defect, not the repair.** If repair genuinely cannot
  preserve a value, that is surfaced, never dropped quietly. Same rule as 3.2.
- **Nondeterminism means the test must be able to fail.** A single passing run
  proves nothing here. Reproduce the loss deliberately before claiming a fix.

### 3.6 Versioning: mint on run, never on edit

A confirmed run mints exactly one `IdeaVersion`. Edits to a pending card mint
nothing, however many there are, per decision memo section 16.2.

This is the write path for
[`2026-08-07-compare-your-own-work.md`](2026-08-07-compare-your-own-work.md).
Comparison is only as trustworthy as versioning is honest: a dropped compound
edit produces a version record that misstates the experiment, and the user's
own history becomes unreliable. Getting the timing backwards instead fills that
history with phantom versions from abandoned edits.

Material change is defined once, here, and consumed by comparison. There is no
second definition anywhere.

## 4. Open decision for the founder

**Does a confirmation-card edit mint a new `IdeaVersion`?**

Decision memo section 16.2 states that one material experiment definition maps
to one immutable `IdeaVersion`, that material changes include assets, date
range, benchmark, rules, cadence, capital, and modeled costs, and that multiple
edits before one confirmed run collapse into a single version.

Read literally, that last clause resolves it: edits made while a card is still
pending collapse, so no version is minted until the run is confirmed. This spec
assumes that reading. It needs an explicit confirmation, because the alternative
silently changes what product memory records for every edited experiment, and
item 4 depends on that record being right.

## 5. Non-goals

- No new modal, toast, wizard, or parallel edit surface.
- No regex or hardcoded language gates for parsing edits. Interpretation stays
  LLM-first.
- No auto-run. Every path still ends at an explicit confirmation.
- Retiring the two scoped buttons is out of scope until section 3.2 is proven.

## 6. Acceptance

- A compound edit in one turn applies every requested change, or names each
  unapplied one with a reason. Proven in English and es-419.
- A scoped entry point followed by a broadened request serves the whole
  request. This is the alpha case; it becomes a regression test.
- Direct capital and date edits spend no turn, create no job, and produce no
  backtest row.
- A direct edit and the equivalent conversational edit produce an identical
  canonical artifact.
- Flag-off behavior, if the lane ships behind one, is byte-identical to today.
- Browser proof in both languages on web and mobile widths.

## 7. Sources

- `docs/specs/argus-active-roadmap.md` board item 2.
- `docs/specs/private-alpha-next-decision-memo.md` sections 16.2 and 21.
- `.agent/designs/argus/DESIGN.md` sections 17, 18, 19.
- Implementation: `src/argus/api/schemas.py`,
  `web/components/chat/StrategyConfirmationCard.tsx`, and
  `src/argus/agent_runtime/stages/interpret_internal/` (`contextual_merge.py`,
  `confirmation_artifact_edits.py`, `date_contract.py`, `asset_resolution.py`).
- Issues #335, #141, #237.
