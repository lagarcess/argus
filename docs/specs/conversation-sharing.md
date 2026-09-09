# Sharing a conversation, not only a backtest

Draft 2026-09-03. Base `codex/private-alpha-next` at `5d408acf`. Written after
driving the built receipt flow end to end; that assessment is at
[`docs/reports/evidence/receipt-sharing/2026-09-03-end-to-end-assessment.md`](../reports/evidence/receipt-sharing/2026-09-03-end-to-end-assessment.md).

This spec widens
[`2026-08-07-sharing-evidence-receipts.md`](../superpowers/specs/2026-08-07-sharing-evidence-receipts.md).
Everything that spec locked stays locked except one line, §7.5's "research
answers not at all", which section 3 asks the founder to overturn on stated
terms. No product code ships from this lane.

## 0. The answer

**Build the research receipt first: one grounded answer, frozen as its own
public page on the pipeline that already exists.** Not a whole conversation,
and not more work on the backtest receipt, which is built and verified.

Why that order:

- A grounded answer is the thing a stranger can read in thirty seconds and
  learn something from. A backtest receipt shows what happened to an idea;
  the research receipt shows what Argus found and where, dated. That is the
  hook the founder named, and it does not exist in any shareable form today.
- It reuses every hard part that is already built and now proven: the
  immutable snapshot table, the closed payload discipline, the tombstone, the
  Shared links list, the funnel, the flag gate, noindex, rate limits, and the
  revoke-on-delete triggers. The build is a second payload kind, a second
  owner endpoint, and a second page body. One flag, one list, one tombstone.
- Its risk is bounded to one message pair. A whole conversation is the
  largest surface Argus could publish and the shape that produced the ChatGPT
  and DeepSeek incidents. Argus threads are also mostly clarify-and-confirm
  plumbing; the compelling unit is the turn, not the thread.

The five hard questions, answered in one place. Each has its own section.

| Question | Answer |
| :--- | :--- |
| What freezes, what stays live | Everything about the content freezes at creation: question, answer, sources with their dates, the retrieval date, symbols, the offered next step, the note. Only the chrome is live: the reader's language, the tombstone state, the call to action. Nothing is re-fetched, ever. The retrieval date is the headline fact, not a footnote. |
| What a guest can share | Nothing. The sole header entry is available to registered owners; the former guest-turn conversion hook is dormant. A public page cannot outlive its owner, a guest's owner row is deleted in seven days, and the snapshot's owner is immutable by trigger, so a guest share would either die at day seven or need the one rewrite the immutability rule forbids. |
| The shared link when the source is gone | The link becomes the tombstone, on the same trigger that already handles backtest receipts. Deleting the chat revokes; account deletion and guest cleanup cascade; restoring a deleted chat does not un-revoke. Argus gains its own takedown reason. |
| What is redacted | The payload is closed and every field is named. Refused, never redacted: a turn whose question or answer carries an identifier or a credential shape, a turn that used memory, a degraded turn, a turn with no typed sources. Dropped by construction: usage, cost, latency, provider and tool names, capability class, shape, peers, follow-up, every id. |
| Can a recipient fork it | No. No fork, no copy, no prefilled prompt. The page shows what Argus offered to test next as text, and the one action lands on guest entry, exactly as the backtest receipt does. A typed "test this yourself" seed is the only fork that fits Argus and is deferred until the funnel shows readers want it. |

## 1. Reference point: how DeepSeek shares a chat

What is documented, from the sources at the end:

- **Creation.** In the web app, the chat's menu offers Share. The user ticks
  the messages to include, or Select all, and taps Create public link. The
  link is copied on creation. Web only; the mobile app cannot create one.
- **The page.** A read-only transcript of the selected turns at
  `chat.deepseek.com/share/<id>`. Anyone with the link can read it.
- **Management.** Settings, Data, Shared links, Manage lists every link with
  a delete control and warns that nobody can open a deleted one.
- **Indexing.** No `noindex`. Researchers found roughly 2,000 shared pages in
  Google's index during 2026, with the largest concentration in April,
  including commercial code, work assignments and financial discussions.
- **Continuation and expiry.** Neither is documented. The page is a
  transcript, not an entry point.

ChatGPT, for the two questions DeepSeek's docs do not answer: a share is a
snapshot at creation and later messages need an explicit Update link; the
"continue this conversation" button was deprecated, and a recipient who
replies gets a private copy in their own history that survives deletion of
the original share.

What Argus takes from DeepSeek: the turn as the unit of selection, the
management list as a first-class control, copy on create. What Argus rejects:
the transcript as the payload, indexability, any "update" that makes a link
live, and copy-into-history forks.

## 2. The three candidates

| | Single turn (research receipt) | Whole conversation | Backtest receipt |
| :--- | :--- | :--- | :--- |
| Value to a stranger | A dated, sourced answer to a question they might have themselves | Mostly plumbing turns around one or two payloads | A number and a chart with the rules that produced them |
| What it freezes | One question, one answer, sources, retrieval date | N turns of free text plus every card kind | Typed facts from an immutable run |
| Free-text channels | Question, answer, note | Every user message, every answer, note | Note only |
| Leak surface | One message pair, closed payload | The transcript, which is where ChatGPT and DeepSeek leaked | Closed payload, proven |
| Staleness | Decays; the date must lead | Decays unevenly by turn | Never decays |
| Build | Second kind on the existing pipeline | New selection UI, new renderer, per-turn eligibility anyway | Done, dark, verified |
| Blocked on | Founder overturning §7.5; rail on (it is) | Research receipts measured first | Founder enable decision |

The whole-conversation share is a sequence of turn receipts or it is nothing
safe. Once per-turn eligibility exists, the thread is a later composition of
it, not a different design. Section 9 keeps its shape on record.

## 3. Overturning §7.5 on stated terms

§7.5 excluded research answers because they "carry third-party claims into a
page Argus publishes under its own domain, permanently, with no correction
path once frozen." The concern is right; the conclusion assumed a page that
presents claims as Argus's own and never says when they were true. The
research receipt is designed so that neither holds.

- **The page is a dated record of what sources said, not a claim.** The
  retrieval date is the stamp in the header, the sources are listed with
  their own dates, and the framing says in plain words that this is what
  those sources reported on that date and that things may have changed since.
  Argus already shows these exact claims, with these exact sources, to the
  person who asked. The receipt adds an audience and a date, not a new claim.
- **There is a correction path.** Revocation, by the owner from Shared links
  and by Argus through a new `removed_by_argus` revocation reason behind the
  report path §7.4 already requires before public exposure. The correction
  for a frozen page is removal and a fresh share, never an edit. That is the
  same rule the backtest receipt already follows.
- **Nothing on the page is a number Argus computed from the sources.** No
  price, no valuation, no simulation. The truth boundary in
  `docs/API_CONTRACT.md` (research informs, Argus providers execute) is
  untouched: a research receipt cannot launch anything.

**Decision requested from the founder:** replace §7.5's "research answers not
at all" with "research answers, one turn at a time, under section 4 of the
widening spec." Everything else in §7 stands.

## 4. The research receipt

### 4.1 Which turns are eligible

An eligibility rule keyed on typed metadata, never on what the prose looks
like. The assessment recorded an answer about NVDA with three publisher URLs
written into its prose and no typed sources at all; it reads like a research
answer and must not be shareable, because nothing typed says where its claims
came from.

A turn is eligible when every one of these holds:

- It is a terminal assistant message (`metadata.agent_runtime_turn.terminal`
  true, `status` completed) in a conversation that is not deleted, owned by a
  registered account (`can_save_decision`).
- It carries `metadata.research` with `schema_version` `argus_research/v1`,
  at least one entry in `sources`, no `degraded`, and a `shape` other than
  `fast` and `find`. A quote with no publisher is not a receipt; a discovery
  answer is a list of tickers, not an answer.
- It carries no `memory_recalls`. An answer shaped by what Argus remembers
  about the owner is personal by construction.
- Its question is the user message the turn answered: the immediately
  preceding user message, or for a background research job the request
  message the job names. One pair, one receipt.
- The question, the answer, and the note each pass the same audit the owner
  note passes today: no identifier, no credential shape, no private id, no
  never-expose marker. Refused, not redacted, and the owner is told which of
  the three tripped it.
- Every URL in the answer prose appears verbatim in `sources`. The rail's
  prompts already forbid authored citation lines; this is the check that
  makes that a property rather than a hope.

Shapes that do not exist as typed rail output are ineligible by construction.
That covers the personal money shape in
[`2026-08-12-personal-money-questions-and-teaching-the-methodology.md`](../superpowers/specs/2026-08-12-personal-money-questions-and-teaching-the-methodology.md):
when it lands with a typed code, it is added to the excluded set explicitly,
and until then it cannot pass.

### 4.2 The payload

`schema_version` 2 introduces `kind`. Version 1 rows are backtest receipts and
stay readable unchanged. Every model keeps `extra="forbid"`.

```text
kind:                 "research_answer"
question:             str        author text, whitespace-normalised, at most 500 characters, refused if longer
answer:               str        author text, at most 4,000 characters, the rail's markdown subset, refused if longer
sources:              list       1 to 5 of {title, domain, url, source_date}, exactly the sidecar's typed shape
retrieved_at:         datetime   the sidecar's retrieved_at
anchor_symbols:       list[str]  at most 5
asset_class:          equity | crypto | currency_pair | null
offered_next_step:    {kind, symbols} | null   from the turn's next_experiments row, closed kind enum, no send_text
owner_note:           str | null  same rules as today
content_language:     en | es-419  the conversation's language, as today
framing:              "research_snapshot_not_advice"
provenance_mark:      "tested_with_argus"
```

Named and absent, on top of §3 of the original spec: `usage` (invocations,
latency, cost, cache status), `capability_class`, `shape`, `peers`,
`follow_up`, `degraded`, provider and tool names, `next_experiments`
`send_text`, `memory_recalls`, and every message, request, turn, job and
conversation id. The never-expose key and value markers in
`argus.domain.public_excerpts` apply unchanged; `latency`, `cost_usd`,
`provider`, `model` and `token` are already on that list, so a projection that
forgot to drop `usage` fails closed at creation.

`offered_next_step` freezes the typed row, not its label, so the page speaks
the sentence in the reader's language. A kind the page cannot render is
omitted, not refused: it is decoration, not evidence.

### 4.3 The page

Same shell and rules as the backtest receipt: standalone route, phone first,
`noindex, nofollow` permanently, no app chrome, one fixed action bar with the
framing attached to the action.

- **Stamp.** "Argus looked this up on {retrieved date}" in the header, where
  the backtest receipt shows its creation date. Rendered from the frozen
  `retrieved_at` in the reader's locale. The page may also say how long ago
  that was; it is computed at view time from a frozen fact, the same way a
  date format is.
- **Question** as the headline, marked with the content language.
- **Answer** as the body, marked with the content language. The rail's
  markdown subset only.
- **Sources** as a ruled list: title, domain, source date. Links open the
  publisher. The receipt vouches for what the source said on the retrieval
  date, not for what the URL serves today, and the framing says so.
- **What Argus offered next**, as one sentence composed from
  `offered_next_step`: "Argus offered to test buying and holding AAPL." Text,
  not a button. The action bar is the only action.
- **Owner note**, if any, as today.
- **Framing**, stronger than the app's, in both languages: what these sources
  reported on that date; not advice, not a prediction; things may have
  changed since; nothing was bought or simulated here.
- **Preview card.** The card publishes less than the page: wordmark, the
  question truncated to fit, "Looked up {date} · {n} sources", the not-a-tip
  line. The question is author text on a public image, so it inherits every
  rule in section 4.1; a question that fails the audit never reaches a card
  because it never reaches a payload.

The prose stays in the author's language and the chrome follows the reader,
exactly as the title and note do today. A Spanish page with an English answer
is a legitimate state and is marked with `lang`.

### 4.4 The owner's side

The header chain-link opens selection, following the founder's final placement
decision in section 4.5. Sharing one answer means selecting one turn there. Two
additions because prose is not structurally closed the way run facts are:

- **A preview before "Make the link".** The owner sees the exact public
  rendering, on their own screen, before anything is written. The backtest
  receipt could skip this because its payload is typed facts; a question the
  owner typed three days ago cannot.
- **A refusal that names the field.** "The question", "the answer" or "your
  note" carries something that cannot go public. The answer cannot be edited,
  so a refusal on the answer ends there.

Shared links lists both kinds with a kind label and the same controls. The
funnel events carry `kind` so the two receipts can be compared as acquisition
paths, which is the measurement section 9 waits on.

### 4.5 Generalising this to every answer. Founder-decided 2026-09-09.

**This extends the sharing feature that exists. It is not a second sharing
system beside it.** Same `evidence_receipts` records, same `/r/<id>` route,
same Settings list, same revoke, same tombstone, same cascade on delete, same
`noindex`, same rendered preview card. `schema_version` 2 adds `kind`; version
1 rows are backtest receipts and keep rendering unchanged. Anything that reads
like a parallel "conversation sharing" feature has been built wrong.

**The affordance.** A link glyph in the chat header, to the left of the
existing `MoreVertical` in `ChatHeaderMenu`, never inside that menu. Its label
says it shares the conversation rather than that it creates a link, because the
click opens selection and no link exists until turns are chosen. Selecting
turns, then one link, is the DeepSeek shape and it is the one we want.

**Final placement decision. Founder, 2026-09-09.** Sharing has exactly one entry
point: the header chain-link. It opens selection; sharing a single answer means
one checked turn on that screen. Remove persistent share pills, add no share item
to message overflow, and remove the visible share control from
`StrategyResultCard`. Sharing is flag-off in production, so preserving the card's
button does not protect an existing user flow. `ShareReceiptAction`'s creation
logic stays behind the selection screen: one creation owner, one place showing
why turns are ineligible, and one user path to verify. This supersedes the earlier
card exception and the proposed message-overflow shortcut.

**Selection within one conversation supersedes section 9's deferral. Founder,
2026-09-09.** Section 4.2 defines one question and answer pair and section 9
defers composition; this resolves that conflict rather than leaving it to the
implementation. A shared thread is **a closed outer `turns` wrapper over
payloads that are exactly what 4.2 specifies**, which is section 9's own design
and not a new shape. Every turn passes 4.1 independently at creation and one
refusal refuses the thread, so a thread can never carry what a single receipt
could not. **Capped at four turns.** Section 9 stays deferred for everything
beyond selection inside one conversation.

**The risk this accepts, named rather than waved at:** three turns that are each
individually safe can identify someone together, and no per-turn audit catches
that. The cap bounds it and the owner sees exactly what they are publishing
before confirming; it is not eliminated.

**Selection is where Argus differs from every competitor, and it is the work.**
They can offer "select all" because every turn is shareable. Ours are not:
section 4.1 refuses clarifications, confirmations, degraded turns, turns shaped
by `memory_recalls`, and turns whose prose carries a URL absent from the typed
sources. **An ineligible turn renders unselectable with a reason the owner can
read**, in their language, or the screen looks broken and sharing reads as
flaky. "Select all" means all eligible and says so.

**One creation owner.** The existing receipt creation logic now serves the
selection screen. The artifact endpoint adapts into the same message eligibility
and singleton identity, so an existing receipt is reused rather than creating
another lineage. The result card's visible control is removed under the final
placement decision above. Records, ownership, Settings and revocation stay in the
existing receipt system.

**The public page stays a receipt, not a rendered card.** `ReceiptBody`'s form
is deliberate: ruled rows and a record stamp, because the page has to argue for
its numbers to someone who never arrived through Argus. That judgment stands.
What changes is where its content comes from: the card's typed facts rather
than `receiptPlan` and `benchmarkVerdict`. Same form, any kind. If a second
calculation needs its own receipt body, operating rule 3 has failed and the
board stops.

**The call to action reads "Continue with Argus."** It lands on guest entry
with no carried state, as today. A bare arrow to `/` is the weakest part of a
loop that is otherwise complete, and this is copy rather than engineering; the
funnel events to measure it already exist.

**Deferred on purpose, not forgotten.** A shared answer that offers its own
re-run, saying what was true on the day and what has happened since, is
something a product that shares prose cannot do and one that shares a
computation can. It contradicts "everything freezes at creation" in section 5,
so it is a later decision taken deliberately, not a tweak inside this work.

---

## 5. Freeze versus live

| Frozen at creation | Live at view |
| :--- | :--- |
| Question, answer, sources with their dates and URLs, retrieval date, symbols, asset class, offered next step, owner note, creation date | Reader's language for chrome, labels, date and number formats |
| The status a link had when it was read last: available or revoked | Whether the link is available or revoked now |
| | The call to action and where it lands |

Never re-fetched, never refreshed, no "update link". If the owner asks the
same question again next month, that is a new turn and, if they choose, a new
receipt; the old one keeps saying what it said on its date. This is the
opposite of ChatGPT's Update link on purpose: a page whose content can change
after it was sent is a page nobody can vouch for.

Source URLs are the one thing on the page that is live by nature, because they
belong to publishers. The receipt does not claim the URL still says what it
said. The framing states that plainly rather than pretending otherwise.

## 6. Guests and the seven-day workspace

A guest cannot create a share of any kind. The final header-only design removes
the former per-turn conversion entry: the existing owner header is available
after registration, and the owner then selects answers normally. The typed
`share_result` pending action and its verified message-target resume remain
compatible but dormant; the header does not invent a message target for a guest.
There is no visible guest share control in this lane.

Three facts decide this:

1. **A public page cannot outlive its owner, and a guest's owner row is
   deleted.** `public_excerpt_snapshots.owner_id` references `profiles` with
   cascade delete, and guest cleanup deletes the anonymous Auth user, which
   cascades. A guest-created link would become an unknown-id tombstone at day
   seven, spread by people who cannot see the clock.
2. **The owner of a snapshot is immutable by trigger.**
   `prevent_public_excerpt_immutable_update` rejects any change to
   `owner_id`. The guest handoff transfers product rows by rewriting their
   owner; the one row it could not transfer without weakening that trigger is
   the public one. Weakening it reopens "who owns this public page", which is
   the question the whole design exists to keep closed.
3. **An anonymous identity minting pages under Argus's domain is the abuse
   shape §7.4 rate-limits but cannot attribute.** The creation limit is keyed
   by user and by client identity; a fresh guest is a fresh user.

What still works: a receipt created after conversion from a turn that was
made as a guest is ordinary, because conversation, message, run and evidence
ids do not change on claim (`docs/DATA_MODEL.md` §5.2). Nothing about the
workspace clock touches a receipt, because a receipt can only exist once the
clock no longer applies.

The registered-owner header is the sole entry. The 403 mapping in
`receiptFailureReason` still distinguishes account conversion from a retryable
error for compatibility callers. A new visible guest conversion hook would be
a separate placement decision; it must not restore a per-turn control.

## 7. When the source goes away

| Event | Backtest receipt today | Research receipt |
| :--- | :--- | :--- |
| Owner revokes from Shared links | `owner_revoked`, immediate, one way | Same |
| Owner deletes the chat (soft delete) | `source_deleted` by trigger; proven in the assessment | Same trigger; the snapshot carries `source_conversation_id` |
| Owner deletes all chats | Same | Same |
| Deleted chat is restored | Stays revoked; revocation cannot be reversed; the owner shares again and gets a new link | Same |
| Owner deletes the account | Cascade removes the row; the link answers as unknown, which is the tombstone | Same |
| Guest cleanup hard-deletes a chat | Trigger revokes, then cascade removes | Same |
| A run is deleted | Not a user action; runs are immutable. Ops deletion revokes by trigger | Not applicable; a research answer has no run |
| A message is deleted | Not a user action; messages are immutable | Every selected message participates in the existing revocation function. The frozen snapshot and private provenance remain so the tombstone outlives the source |
| A source retracts or a claim proves wrong | Not applicable | Revocation by owner or by Argus (`removed_by_argus`). The date stamp is the standing correction; the page never edits |
| The owner re-runs or re-asks | The old receipt does not move | Same |

A revoked link, of either kind, answers the same tombstone as an unknown id,
and the tombstone keeps the call to action. The list keeps the reason in the
owner's words: taken down by you, taken down when you deleted the chat, or
removed by Argus.

## 8. Fork

A recipient cannot continue the conversation. No copy into their history, no
prefilled composer, no carried state.

- §7.2's reasoning holds for a research answer more than for a backtest: the
  receipt already answered the question, replaying it teaches nothing and
  spends a guest run doing it.
- ChatGPT's copy-on-reply fork imports frozen text into the recipient's
  account. Argus has no equivalent that is not a prompt: every turn re-grounds
  through the interpreter, so a "copy" of a research answer would be a
  prefilled question, which §7.2 rejected.
- Nothing on the page is executable. `offered_next_step` freezes what Argus
  offered as a sentence; `send_text` never leaves the transcript.

What replaces a fork is measurement. Funnel events carry `kind`, so Argus
learns whether readers of research receipts reach a first result more often
than readers of backtest receipts. **Deferred, not built:** a typed seed on
guest entry from the receipt's `anchor_symbols`, so a reader lands on a first
chip that names the asset they just read about without replaying the
question. It is the one fork shape that fits Argus. It waits on the funnel
showing intent and on #402's identifier decision, because it would be the
first thing carried across the hop that §7.2 kept empty.

## 9. Whole conversation, if ever

Selection of up to four turns inside one conversation is authorized by section
4.5. Everything beyond that remains deferred. Any future wider composition is
still a composition of turn receipts, and the
archived Slice 7 design in
`docs/archive/private-alpha-conversation-trust.md` is the shape to reuse with
one change: no raw card payloads, only per-turn closed payloads.

- The owner selects turns; only eligible ones are selectable. Clarifications,
  confirmations, failures, memory-shaped turns and untyped answers are not
  turns a stranger should read, and they are the turns where transcripts
  leak.
- One snapshot, one link, one tombstone, capped at a small number of turns,
  rendered in conversation order as a sequence of receipt blocks.
- Every turn passes section 4.1 independently at creation; one refusal
  refuses the thread.

Preconditions before it is placed on the board: research receipts live and
measured, a report path in place, and the prose audit exercised on real turns
at volume rather than on fixtures.

## 10. Contract changes this needs

The implementation contract follows the founder's section 4.5 selection decision.
`docs/API_CONTRACT.md`, `docs/DATA_MODEL.md` section 12.1.3, and generated OpenAPI
describe the concrete API and persistence shapes. Exposure remains a separate
founder decision; these contracts do not enable the flags.

**Data model, `public_excerpt_snapshots`:**

- `kind text not null default 'backtest'`, closed to `backtest`,
  `research_answer`, and `mixed`.
- Private immutable `source_message_ids`, `source_run_ids` and
  `source_artifact_ids` arrays, bounded by the four-turn selection. The existing
  scalar source columns remain for version 1 compatibility and singleton identity.
- A canonical `selection_key` and partial unique index on `(owner_id,
  selection_key)` for live selections. The existing live-artifact uniqueness
  remains, so both singleton entry points resolve the same record. Re-share after
  revoke mints a new link.
- `revocation_reason` check gains `removed_by_argus`.
- `prevent_public_excerpt_immutable_update` covers `kind`, selection identity
  and all selected source arrays.
- The existing source-liveness and revocation functions cover every selected
  source. A message deletion trigger joins the same function; the conversation
  triggers continue to key on `source_conversation_id`.

**Schemas:** version 1 `PublicExcerptPayload` stays the concrete backtest payload.
Version 2 is a closed `{schema_version: 2, kind: "turns", turns: [...]}` wrapper
whose one to four leaves discriminate on `kind`. Every research leaf is exactly
section 4.2. New singleton shares use the same wrapper. The public view, the owner
list item and the funnel stage each gain
`kind`. `RevocationReason` gains `removed_by_argus`. `GuestConversionReason`
gains `share_result`.

**Endpoints, all behind the same flag and the same 404 byte identity:**

- Owner-scoped candidate, preview and create endpoints under
  `/conversations/{conversation_id}/public-excerpt-candidates`,
  `/conversations/{conversation_id}/public-excerpt-preview`, and
  `/conversations/{conversation_id}/public-excerpt`. Preview/create name one to
  four distinct message ids. Create requires the preview digest and rechecks all
  sources. Typed refusal reason and field appear in the Problem Details context.
  The artifact endpoint adapts into this same service and singleton identity.
- `GET /public-excerpts`, `DELETE /public-excerpts/{id}` and the public read
  are unchanged in shape and gain `kind`.
- An admin-only revoke with reason `removed_by_argus` is specified with the
  report path, not here.

**Web:** one `ReceiptBody` consumes the versioned document through typed
presentation adapters, with unchanged version 1 rendering. The header is the sole
entry point and opens selection, which alone displays disabled turns and their
localized reasons. No message-overflow item, assistant-bubble pill or result-card
share control remains. Shared
links shows the kind; the existing preview image supports research. The typed
403 conversion/resume mapping remains compatible, with no visible guest entry.

**Flags:** none new. `ARGUS_EVIDENCE_RECEIPT_SHARING_ENABLED` and its
`NEXT_PUBLIC_` twin gate both kinds. A research receipt additionally requires
the rail, because a sidecar cannot exist without it, and the rail is on.

**Docs:** `docs/API_CONTRACT.md` Public evidence receipts, `docs/DATA_MODEL.md`
§12.1.3, `docs/api/openapi.yaml`, and §7.5 of the original spec.

## 11. Acceptance

- An eligible research turn renders from its frozen snapshot with no read of
  the conversation, the message, or the provider. Proven by the same
  construction test the public route has today.
- Nothing on the §3 list, plus section 4.2's additions, appears in the
  payload, the page source or the preview image. Proven adversarially over
  real rail turns in both languages, not fixtures.
- An answer with URLs in its prose and no typed sources is refused. The NVDA
  turn from the assessment is the fixture.
- A turn that used memory is refused. A degraded turn is refused. A `fast` or
  `find` turn is refused.
- A question or answer carrying an identifier or a credential shape is
  refused and the refusal names the field.
- The retrieval date leads the page in both languages; the framing is present
  and stronger than the app's; no em dashes in any user-facing copy.
- Deleting the chat revokes; re-sharing after deletion refuses; restoring does
  not un-revoke. Proven against Postgres, as the existing 21 tests do.
- Guests have no share entry and cannot create receipts; previously guest-owned
  turns can be selected after the normal account claim.
- Funnel events carry `kind` and the view is counted once per rendered page.
- Flag-off byte identity holds for the new route.

## 12. Open for the founder

1. Overturn §7.5 as section 3 asks. Without this, nothing in section 4 is
   built.
2. Accept `removed_by_argus` and pair it with the report path before public
   exposure, as §7.4 already requires.
3. The preview card carries the owner's question, which is author text on a
   public image. Keep it, or ship the card with the wordmark, date and source
   count only.
4. Whether the enable decision for the two kinds is one decision or two. This
   spec assumes one flag and one decision.
5. The rail lane should persist a typed sidecar on the search-packet path so
   "why is X moving today" becomes shareable; that is the most common research
   question and it is the one this spec cannot reach today.

## 13. Sources

- Kaspersky, "How to use DeepSeek both privately and securely": creation
  steps and the Settings, Data, Shared links, Manage path.
  https://www.kaspersky.com/blog/deepseek-privacy-and-security/54643/
- Cybernews, "Google is indexing DeepSeek's shared chats": roughly 2,000
  indexed pages in 2026, content classes, deletion path.
  https://cybernews.com/ai-news/deepseek-data-leak-shared-chats-google-index/
- Yowox, "When AI Conversations Become Public: An Analysis of DeepSeek Shared
  Links": per-message selection; indexing observed with a site: search.
  https://yowox.com/posts/deepseek-shared-links-ai-conversations-public/
- Storylane, "How to Share a Chat in DeepSeek": checkbox selection, Create
  Public Link, Create and Copy, web only.
  https://www.storylane.io/tutorials/how-to-share-a-chat-in-deepseek
- OpenAI Help Center, "ChatGPT shared links FAQ": snapshot at creation, Update
  link, continuation deprecated, copy on reply.
  https://help.openai.com/en/articles/7925741-chatgpt-shared-links-faq
- `docs/superpowers/specs/2026-08-07-sharing-evidence-receipts.md` §3, §7.
- `docs/specs/private-alpha-next-decision-memo.md` §5.8, §10.7, §15.7.
- `docs/DATA_MODEL.md` §5.1, §5.2, §8, §12.1.3.
- `docs/API_CONTRACT.md`, Public evidence receipts and Research Responses.
- `docs/archive/private-alpha-conversation-trust.md`, Slice 7.
