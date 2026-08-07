# Sharing: Evidence Receipts

Draft 2026-08-07. **Partial spec.** Sections 1 through 6 are settled by canon or
clear practice, and §7.2, the viewer path, is decided.

**Open decisions remain in §7 and this must not be dispatched until they are
answered:** attribution, abuse posture, what is shareable, the revoked-link page,
and expiry. The viewer path (§7.2) and search indexing (§7.3) are decided.

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

### 7.1 Attribution

Does a receipt name its creator?

Options: anonymous always, optional attribution the owner opts into, or always
attributed. This shapes what sharing socially *is*: a private artifact you
happen to send, or something with your name on it. It also has privacy weight,
since an attributed receipt tied to a real name is a public statement about
someone's investing interest.

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

### 7.4 Abuse posture

Public URLs invite misuse: receipts shared to mislead, screenshots presented as
Argus endorsing a position, or volume-created links.

Needed: whether creation is gated at all, whether there is a report path, and
what takedown looks like. A private alpha with an allowlist has low exposure
today, which is the argument for deciding it now rather than at public launch.

### 7.5 What is shareable

A completed backtest result is the obvious case.

Also a comparison? Also a research answer? Each widens the leak surface
differently, and a research answer in particular carries third-party sources
into a page Argus publishes, which raises attribution and correctness questions
the other two do not.

An earlier draft narrowed this by requiring the artifact be re-runnable. That
constraint came from a viewer path that preloaded the setup, which 7.2 rejected.
Nothing is carried now, so re-runnability no longer bounds the answer.

Recommend starting with results only and widening once the funnel is measured.

### 7.6 Revocation semantics — partially decided

**Decided, from prior art:** deleting the underlying idea or run must revoke the
receipt. ChatGPT's failure mode is that deleting the source chat leaves the
public page live, so a user who believes they removed something has not. That is
a trap, and it is avoidable by making revocation follow deletion automatically.

**Decided:** revocation takes effect immediately on Argus's side.

**Still open:** whether a revoked link returns 404 or an honest "no longer
available" page. A tombstone does not look broken, but it confirms the link once
existed, which is itself a small disclosure.

**Honest limit to state in the product, not just here:** social platforms cache
preview cards. A revoked receipt can survive as a preview in a message thread
after the page is gone. Argus cannot fix that, so it should not imply otherwise
when someone revokes.

### 7.7 Expiry

Do receipts live forever by default, or expire? Permanent links are better for
distribution and worse for control.

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
