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
| What a guest can share | Nothing. The share tap on a guest turn is a conversion hook, not a share. A public page cannot outlive its owner, a guest's owner row is deleted in seven days, and the snapshot's owner is immutable by trigger, so a guest share would either die at day seven or need the one rewrite the immutability rule forbids. |
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

The share action appears on an eligible research answer where the backtest
action appears on a result card: same component, a second kind, never a
second vocabulary. Two additions because prose is not structurally closed the
way run facts are:

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

A guest cannot create a share of any kind. The share tap on a guest's
eligible turn is a conversion hook: it raises the existing
`account_conversion_required` flow with a new `GuestConversionReason`
`share_result` and a pending action that names the message, so that after the
claim the share panel reopens on that turn and the receipt is created under
the permanent account.

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

The current UI hides the action from guests. This spec replaces hiding with
the conversion prompt, and fixes the 403 mapping in `receiptFailureReason` so
the answer is honest rather than "try again".

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
| A message is deleted | Not a user action; messages are immutable | Same. `source_message_id` is `on delete set null` so a tombstone outlives whatever it pointed at, matching the other source columns |
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

Not now. If it is ever built, it is a composition of turn receipts, and the
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

Recorded here so the build lane starts from a contract, per
`docs/API_CONTRACT.md` first. No code in this lane.

**Data model, `public_excerpt_snapshots`:**

- `kind text not null default 'backtest' check (kind in ('backtest', 'research_answer'))`.
- `source_message_id uuid null references messages(id) on delete set null`.
- Partial unique index on `(owner_id, source_message_id) where revoked_at is
  null and source_message_id is not null`: one live receipt per turn,
  re-share after revoke mints a new link, exactly as for artifacts.
- `revocation_reason` check gains `removed_by_argus`.
- `prevent_public_excerpt_immutable_update` covers `kind` and
  `source_message_id`.
- No new revocation trigger: the conversation triggers already key on
  `source_conversation_id`, and messages are never deleted on their own.

**Schemas:** `PublicExcerptPayload` becomes a discriminated union on `kind`
with `schema_version` 2 for the research kind; version 1 stays the backtest
payload. The public view, the owner list item and the funnel stage each gain
`kind`. `RevocationReason` gains `removed_by_argus`. `GuestConversionReason`
gains `share_result`.

**Endpoints, all behind the same flag and the same 404 byte identity:**

- `POST /messages/{message_id}/public-excerpt`, owner, registered only, same
  body and rate limits as the artifact route, same idempotency on a live
  receipt, same error codes plus `receipt_source_unsupported` for an
  ineligible turn with the field named in `detail`.
- `GET /public-excerpts`, `DELETE /public-excerpts/{id}` and the public read
  are unchanged in shape and gain `kind`.
- An admin-only revoke with reason `removed_by_argus` is specified with the
  report path, not here.

**Web:** `/r/[receiptId]` branches on `kind`; the share action generalises to
the research answer message; Shared links shows the kind; the preview image
renders the research card; the 403 mapping becomes the conversion prompt.

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
- A guest's share tap raises the conversion prompt and nothing is written.
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
