# Sharing: Evidence Receipts

Draft 2026-08-07. **Partial spec.** Sections 1 through 6 are settled by existing
canon or by clear practice. Section 7 lists what needs founder decisions before
this can be built. Do not dispatch until section 7 is answered.

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

**To guest mode.** The viewer path is where sharing meets acquisition. See §7.2,
which is the decision that determines whether this pillar produces growth or
just produces links.

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

### 7.2 What the viewer can do

A stranger opens the link. Then what?

Options: read-only with a sign-up call to action, read-only with a "test this
yourself" path straight into guest chat with the setup preloaded, or a wall
requiring sign-up to see anything.

**This is the most consequential decision in the pillar.** The third option
kills the loop. The second is the strongest acquisition mechanic and fits the
guest-first stance, since a first completed backtest is activation. The first
is safest and slowest.

### 7.3 Search indexing

Should receipts be crawlable?

Indexing creates a discovery channel and compounds over time. It also means
someone's shared idea is permanently findable, which changes the privacy posture
of every previous decision, and it interacts with attribution.

### 7.4 Abuse posture

Public URLs invite misuse: receipts shared to mislead, screenshots presented as
Argus endorsing a position, or volume-created links.

Needed: whether creation is gated at all, whether there is a report path, and
what takedown looks like. A private alpha with an allowlist has low exposure
today, which is the argument for deciding it now rather than at public launch.

### 7.5 What is shareable

A completed backtest result is the obvious case. Also a research answer? A
comparison? An idea with no run?

Each widens the leak surface differently, and a research answer in particular
carries third-party sources into a page Argus publishes.

### 7.6 Revocation semantics

Owner-revocable is locked. The behavior is not.

Does a revoked link 404, or show an honest "no longer available" page? A
tombstone is kinder and does not look broken, but it confirms the link once
existed, which is itself a disclosure. Also: social platforms cache previews, so
a revoked receipt can survive in a preview card after the page is gone. Whether
that is acceptable needs saying.

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
