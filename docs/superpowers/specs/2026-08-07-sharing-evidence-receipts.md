# Sharing: Evidence Receipts

Draft 2026-08-07. **Partial spec.** Sections 1 through 6 are settled by canon or
clear practice, and §7.2, the viewer path, is decided.

**All §7 decisions are now made.** This spec is complete and dispatchable when
the pillar comes up, subject to the standing rule that it ships last of the
five.

Board pillar 5. Deliberately last of the five: sharing a broken loop spreads a
bad impression faster than a good one.

## 1. What it is

A shared Argus link is an **immutable, sanitized evidence receipt**, not a
conversation link and not a live view into anything.

Decision memo §10.7 locks the pipeline:

```text
EvidenceArtifact -> PublicExcerptSnapshot -> PublicExcerptView
```

The snapshot is immutable, owner-created, and owner-revocable. **The public
layer never queries the original private conversation.** It renders a
purpose-built payload frozen at creation.

Immutable means the numbers never move. If the owner re-runs the idea later, the
receipt still shows what it showed the day it was shared. That is what makes it
a receipt rather than a dashboard.

## 2. The payload

Locked by §10.7. A receipt carries:

- idea title
- asset and asset class
- strategy and assumptions
- date range
- result metrics
- visual evidence
- educational and not-advice framing
- optional owner note

Nothing else.

## 3. What must never appear

Locked by §15.7, and this list is absolute:

- source conversation ids
- route receipts
- provider or model metadata
- retry payloads
- raw transcripts
- broker or account data
- user-private memory

Memory in particular is never shared under any circumstance, including when the
owner wants to. A memory is Argus's inference about a person; it is not theirs
to publish about themselves through this surface.

## 4. Framing, and why it is stronger in public

The not-advice framing must be **more prominent in a receipt than in the app**,
not less.

An app user has context: they built the experiment, they saw the confirmation
card, they know it is a historical simulation. A receipt viewer has none of
that. They arrived from a message with no idea what Argus is, and they are
looking at investment-shaped numbers.

So the receipt states plainly that it is a historical simulation, not advice,
and not a prediction. The existing `chat.disclaimer` line is the floor, not the
ceiling.

## 5. Practice that is not in canon but is not in doubt

**Social preview is table stakes.** A link pasted into a message renders a card.
Without Open Graph metadata it renders as a bare URL and the distribution loop
dies at the first hop. Note that the preview image is itself a public artifact
and inherits every rule in section 3.

**Mobile first, unlike the rest of Argus.** Shared links are opened
overwhelmingly on phones, from messaging apps. The public view should be
designed for a phone and scale up, which is the inverse of the app's current
posture. It also means the public view does not wait on the mobile PWA lane;
it is a separate surface with its own layout.

**Copy link is the primary action.** Not a native share sheet, which behaves
inconsistently and buries the URL.

**The truth boundary holds.** Result metrics come from the frozen evidence
artifact. A receipt never shows a live price, never calls a provider, and never
enriches with research at view time. It is a record, not a page that thinks.

## 6. Relationships, stated so they cannot drift

**To comparison.** A comparison reads several artifacts. Whether a comparison is
shareable is an open decision (§7), but if it is, it is one snapshot of the
comparison, never a bundle of links.

**To memory.** Never shared. See §3.

**To the research rail.** A receipt is frozen and offline. If a receipt ever
carried research context, that context is frozen into the snapshot at creation
with its sources, never fetched at view time.

**To guest mode.** The viewer lands on the standard guest entry with nothing
carried across (§7.2). Sharing adds no new entry state and no new parameter to
that surface; it is an ordinary first visit that happened to arrive from a
link.

**To mobile.** The public view owns its own responsive layout and does not share
the app shell.

## 7. Open decisions, founder

None of this can be built until these are answered. They are product and
posture calls, not engineering ones.

### 7.1 Attribution — DECIDED 2026-08-07

**Anonymous. A receipt never names its creator, and there is no opt-in toggle.**

Investing interest is sensitive personal information. An attributed receipt is a
public statement about someone's risk appetite, wealth, or a position that could
conflict with their employment. That is a poor default for a product whose users
are testing ideas privately.

An opt-in toggle is worse than either extreme, and for the same reason a
discoverability toggle failed at ChatGPT: it places an irreversible decision
behind a control read once, and the consequence lands long after the click.

Attribution also serves the sharer more than the viewer. A viewer cares about
the idea, not who produced it.

If attribution is ever wanted, it is a deliberate later design with its own
consent flow, never a checkbox added to this surface.

### 7.2 What the viewer can do — DECIDED 2026-08-07

**Read-only receipt, one "Try Argus" call to action, landing on the standard
guest entry.** Nothing is carried across.

No wall, no sign-up gate, no preloaded state.

**Why nothing is carried.** Prefilling the receipt's own question was considered
and rejected: the receipt already answered it. Replaying it makes a newcomer's
first Argus experience a reproduction of something they just read, teaches them
nothing, and spends a guest run doing it.

The question a viewer actually arrives with is not "run that again", it is "can
it do something for me". The standard guest entry answers exactly that. Its
starter chips span learn, compare, and test, they are proven runnable, and they
show range instead of replaying one example.

This also removes every problem the alternatives created. Nothing goes stale,
because nothing is carried. No re-grounding, because nothing is resolved. No
honesty caveat about frozen numbers versus a fresh run. No extra parameterization
of the entry surface.

**Consequences that still hold:**

- **Viewer runs spend guest allowance**, sized for organic rather than viral
  traffic. Confirm ceilings hold before enabling broadly, and make exhaustion an
  honest message rather than a broken first impression.
- **The path is instrumented as the acquisition funnel it is:** receipt created,
  receipt viewed, Try Argus tapped, first result completed. Decision memo
  section 10.6 asks this of the loop, and this is the first surface where it is
  fully observable end to end.
- **Nothing auto-runs**, which is trivially satisfied since the viewer lands on
  an ordinary empty entry.

**Deliberately deferred, do not build:** letting the receipt influence which
starter chip leads, so a comparison reader sees a comparison chip about a
different set. It carries the shape without the subject or the redundancy. The
chips already span the range, so this buys little and the priority now is signal
rather than features.

### 7.3 Search indexing — DECIDED 2026-08-07 by prior art

**Never indexable. `noindex, nofollow` by default, permanently, with no
user-facing toggle that can change it.**

This is not a preference. Both market leaders shipped conversation sharing
without it and both had a public privacy incident inside the last year.

- **ChatGPT** shipped a "make discoverable" toggle. Roughly 100,000 shared
  conversations were exposed through search engines. Users did not understand
  what the toggle meant.
- **Claude** shipped share links with no noindex tag at all. Shared chats
  surfaced in Google and Bing results, some containing API keys and personal
  data. Anthropic's position was that it worked as intended.

A discoverability toggle is the specific failure. It puts an irreversible
decision behind a control the user reads once, and indexing cannot be undone:
caches and archives persist long after the page is revoked.

Argus is structurally safer because a receipt is a sanitized structured artifact
rather than a transcript, so there is no free-text channel for a user to
accidentally publish a credential. **The one exception is the optional owner
note in §2**, which is genuinely free text. Treat it as the only place this
class of accident can happen, and consider whether it needs a length bound or a
warning.

Any future discovery channel is a deliberate, separately designed surface that
Argus curates. It is never a byproduct of a user sharing a link with a friend.

### 7.4 Abuse posture — DECIDED 2026-08-07

**No creation gate beyond the existing allowlist. Rate-limit creation. Add a
report path before public exposure, not now. Mark the artifact so a screenshot
carries its own context.**

The worst class of sharing abuse, publishing arbitrary user content, is already
prevented structurally: a receipt is a sanitized artifact with a closed payload,
not a transcript. That is the difference between this design and the ones that
had incidents.

The misleading-results risk is real but it belongs to backtesting, not to
sharing. A receipt showing a large return is honest about what happened
historically. The mitigation is the framing in §4, which is deliberately
stronger in public than in the app.

Two things worth building:

- **Rate-limit receipt creation**, so a compromised or careless account cannot
  generate links at volume.
- **A visible "tested with Argus" mark in the rendered receipt and its preview
  image**, so a screenshot carries its own provenance. Screenshots travel
  further than links, and an unmarked screenshot of Argus numbers is the easiest
  way for someone to imply an endorsement Argus never made.

Creation is gated by the allowlist today, which is the real control while the
alpha is closed. A report path and takedown flow are required before public
exposure and are not needed at current scale.

### 7.5 What is shareable — DECIDED 2026-08-07

**Completed backtest results only. Comparisons second, once the funnel is
measured. Research answers not at all.**

A result is the clean case: frozen numbers, closed payload, and it is what people
actually want to show someone.

A comparison is a reasonable second because its members are also frozen
artifacts, but it references several runs and widens the surface. Wait until
there is evidence anyone wants it.

**Research answers are excluded on a different basis, not merely deferred.** They
carry third-party claims into a page Argus publishes under its own domain,
permanently, with no correction path once frozen. If a provider was wrong, Argus
is the publisher of that error. That is a different risk class from publishing
your own simulation results, and the sharing value is lower anyway: the
interesting artifact is what would have happened, not what an article said.

### 7.6 Revocation semantics — partially decided

**Decided, from prior art:** deleting the underlying idea or run must revoke the
receipt. ChatGPT's failure mode is that deleting the source chat leaves the
public page live, so a user who believes they removed something has not. That is
a trap, and it is avoidable by making revocation follow deletion automatically.

**Decided:** revocation takes effect immediately on Argus's side.

**Decided: an honest tombstone, not a 404.** The concern with a tombstone is
that it confirms the link once existed, but the person opening it already holds
the link and knows someone sent it. With unguessable ids there is no enumeration
risk, so the tombstone discloses nothing the viewer does not already have.

A 404 reads as broken and makes the sender look careless. The tombstone says the
receipt is no longer available and still offers Try Argus, since a visitor who
followed a link has already shown intent.

**Honest limit to state in the product, not just here:** social platforms cache
preview cards. A revoked receipt can survive as a preview in a message thread
after the page is gone. Argus cannot fix that, so it should not imply otherwise
when someone revokes.

### 7.7 Expiry — DECIDED 2026-08-07

**No automatic expiry. Owner-revocable, and the owner can see everything they
have shared.**

A receipt is a frozen historical record. Unlike a conversation it does not decay
in accuracy, so time-based expiry would break saved links without making anything
safer. Both ChatGPT and Claude also ship without expiry; that part of the norm is
fine.

**The part they got wrong, and the actual requirement here:** users could not
easily audit what they had shared. That is a large reason the ChatGPT exposure
was as bad as it was, with people surprised by links they had forgotten
creating.

So a receipt list is not a nicety, it is the control that makes owner-revocable
meaningful:

- every receipt the user has created, in one place
- when it was created and what it shows
- revoke from that list, in one action
- reachable from Data Controls, where the rest of the user's data controls live

Without it, "owner-revocable" is true in the API and false in practice.

## 8. Acceptance, once §7 is answered

- A receipt renders from the frozen snapshot with no call to the private
  conversation, proven by test.
- Nothing on the §3 list can appear in the payload, the preview image, or the
  page source. Proven adversarially, not asserted.
- Numbers do not change when the underlying idea is re-run.
- Revocation takes effect immediately by the agreed semantics.
- The receipt reads correctly on a phone first.
- Not-advice framing is present and prominent, both languages.
- No em dashes in user-facing copy in any language.

## 9. Sources

- `docs/specs/private-alpha-next-decision-memo.md` §10.7, §15.7, §16.3, §21.
- `docs/specs/argus-active-roadmap.md`, pillar 5.
- `.agent/designs/argus/DESIGN.md` §17 and §19 for the public view's touch and
  accessibility floors.
- `docs/superpowers/specs/2026-08-07-compare-your-own-work.md` for the
  comparison artifact, should §7.5 include it.
