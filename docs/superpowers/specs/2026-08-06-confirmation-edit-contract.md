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

**Build order, and it is not the section order.** Sections are numbered by what
the contract says, not by what gets built first. The lane builds in this
sequence:

1. **3.4, in-place drawers for capital and dates.** Additive, removes nothing,
   and depends on nothing else here. A drawer hands over a typed number or date,
   so deterministic code computes from it and no prose is parsed at all, which
   is 3.5b in its cleanest form. This lands first so the lane delivers something
   visible early rather than at the end.
2. **3.2, compound edits never drop silently**, together with 3.5 and 3.5b.
   Those two are the same defect wearing different clothes and are fixed as one
   theme.
3. **3.3, scoped entry points accept broader edits.**
4. **3.1, retiring the two scoped buttons.** Last, and only once 3.2 is proven.

The order is driven by risk, not preference. The drawers add a path, so shipping
them early costs nothing if the rest slips. Retiring the buttons removes the only
edit paths that currently work, so it cannot go first without making the alpha
failure more common.

3.6, versioning, is not sequenced here. It must be true before the lane closes,
because item 4 on the board reads the records it writes.

### 3.1 Three actions

The end state is **Run backtest**, **Change/edit assumptions**, **Cancel**.

`change_dates` and `change_asset` are retired as buttons.
Change/edit assumptions becomes the only entry point to editing anything.

**This is gated on section 3.2 being true first, and it is the last thing the
lane builds.** See the build order above. The retired buttons are
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

### 3.4b Amendment 2026-08-10: one in-flow drawer at every width

**This amendment is binding and supersedes the mobile row of the table above.**
During the founder's hands-on review the sheet path failed in the exact way a
second primitive fails: `BottomSheet` renders fixed-position without a portal,
so inside the card's transform containing block it clipped into a view
takeover that replaced the card. The founder's direction was one disclosure
idiom, no exceptions.

The shipped behavior at every width is the editable `ExecutionDetails` shape:
the pill row stays where it is, the drawer expands downward in normal flow
inside the card, pushing the content below it down, and closing rolls it back
up. The mobile sheet reservation in the responsive-shell spec is unused by
this surface. A drawer with more fields is simply taller; the layout never
changes.

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

### 3.5b Dates: the LLM interprets, deterministic code computes (#332)

`argus.nlp.natural_time.parse_date_text` mishandles fractional durations. It
reads the digit after the decimal point as the whole quantity and discards the
integer part. Probed against reference date 2026-08-01:

| input | resolves to | equivalent to |
| --- | --- | --- |
| `8.5 months ago` | 2026-03-01 | 5 months ago |
| `3.5 months ago` | 2026-03-01 | 5 months ago |
| `2.5 months ago` | 2026-03-01 | 5 months ago |
| `5 months ago` | 2026-03-01 | correct |
| `2 months ago` | 2026-06-01 | correct |

Every `N.5` collapses to the same date regardless of N. Integer durations are
correct, so the defect is specific to fractional parsing. Asking for 8.5 months
returns 5, a 41 percent shortfall; asking for 2.5 months also returns 5, double
the request.

**Do not patch the fractional case.** The defect is the pattern, not the digit.

This repo forbids regex, hardcoded language gates, and shortcut routing ahead of
LLM interpretation. A deterministic parser guessing at date prose is a second
interpreter competing with the real one, and it will keep losing on phrasings
nobody enumerated. Fractional months are simply the instance that surfaced.

**The macro pattern:**

> The LLM interprets language into a typed value. Deterministic code validates
> and computes from that value. Deterministic code never parses prose.

Concretely, interpretation emits something typed, a unit and a quantity that may
be fractional, and date math runs from that. Arithmetic is exactly what
deterministic code is good at; turning "the last 8.5 months" into a number is
language, and it belongs to the interpreter.

Where prose parsing remains for a legitimate reason, say why and bound it.
Silent prose parsing is the thing being removed.

**This is an editing concern** because changing dates is the most common edit on
the card, and because the failure is the same harm as section 3.2: the user
silently gets a different experiment than the one they asked for. A dropped
compound edit and a misparsed duration land the user in the same wrong place.

Nondeterminism note: verify by probing the parser directly, as above, rather
than through a full turn. LLM interpretation runs first and normalizes some
phrasings, so a passing journey proves nothing about the parser.

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

## 4. Versioning: decided

**Does a confirmation-card edit mint a new `IdeaVersion`? No.** Founder
confirmed 2026-08-10: edits to a pending confirmation card mint nothing;
only run finalization mints an `IdeaVersion`.

Decision memo section 16.2 supports the same reading: one material
experiment definition maps to one immutable `IdeaVersion`, and multiple
edits before one confirmed run collapse into a single version. This is one
face of the contract's record-creation rule, whose dividing line is whether
a turn was spent: non-turn changes update the pending card in place and
mint nothing anywhere; turn-based edits supersede with a new card message
because the conversation records the change; run finalization alone mints
the version.

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
