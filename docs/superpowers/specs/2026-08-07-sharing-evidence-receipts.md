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

### 7.2 What the viewer can do — DECIDED 2026-08-07

**Read-only, with a "test this yourself" path straight into guest chat with the
setup preloaded.**

No wall. A stranger sees the receipt, and one tap puts them in Argus with the
experiment ready. This is the acquisition mechanic and it fits the guest-first
stance: a completed first backtest is activation, not account creation.

Four things follow from this, and they are requirements rather than options.

**It lands on a confirmation card. It never auto-runs.** Argus never auto-runs
anywhere, and a shared link is the worst place to start: the viewer did not
build this experiment and has not seen its assumptions. They arrive at the card,
read what it will do, and choose.

**The setup re-grounds on arrival, and the receipt is honest that it will
differ.** The receipt is frozen; a run happens now. Dates may clamp, coverage may
have changed, an asset may have moved. So the handoff re-validates through
Argus's own providers, exactly as a research-launched test does, and the receipt
says plainly that it was tested on its original date and that running it now
uses current data.

Without that line the viewer expects to reproduce the number they just read and
gets a different one. That reads as Argus being wrong rather than time having
passed, and it is the single most likely way this surface destroys trust.

**A viewer's run spends their guest allowance.** A widely shared receipt sends
many strangers into guest chat, each consuming allowance against limits sized
for organic traffic. Confirm the ceilings hold for viral volume before this is
enabled broadly, and make exhaustion an honest message rather than a broken
first impression.

**The whole path is instrumented as the acquisition funnel it is:** receipt
created, receipt viewed, test-this-yourself tapped, confirmation reached, first
result completed. Decision memo section 10.6 asks exactly this of the loop, and
this is the first surface where the funnel is fully observable.

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

### 7.5 What is shareable — narrowed by 7.2, still open

7.2 constrains this: if the viewer's action is "test this yourself", the shared
thing must be **re-runnable**. That makes a completed backtest result the clear
case, and a comparison plausible since its members are re-runnable.

A research answer is not re-runnable in the same way, and it carries
third-party sources into a page Argus publishes. It would need a different call
to action, which means a second viewer path.

**Still needs a decision:** results only, results plus comparisons, or research
answers too with their own path. Recommend starting with results only and
widening once the funnel is measured.

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
