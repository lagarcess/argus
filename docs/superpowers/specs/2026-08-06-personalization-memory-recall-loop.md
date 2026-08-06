# Personalization Memory Recall Loop

Turns the shipped memory foundation (PR #386) into the interaction users
feel: Argus answers history questions with visible retrieval, recalls
semantically instead of by token match, proposes memories from idle
conversations, splits private chat into read and write controls, and lets
users edit memories from inside the chat.

Founder-locked 2026-08-06, after PR #386 delivered the end-to-end
personalization memory feature (assessor, role gate, Data Controls, recall
notes, export, private chat) and the founder ratified this five-item list
plus the four Mem0 parameters in the design conversation of the same date.

## 1. Why

`docs/PRODUCT.md` section 21: every feature must make it easier to "turn
curiosity into a grounded investing experiment and continue exploring."
Memory serves the continue-exploring half, and this lane closes the gap
between memory existing and memory being felt. Today a user who asks "what
did I decide about ETH?" watches Argus answer "I have no record" while the
correct memory renders in a note below the answer (captured in PR #386's own
QA screenshots). Functionally the recall works; conversationally it reads as
a miss.

The decision memo grounds each item:

- Section 5.6 names decision memory the largest new pillar and locks the
  architecture this lane completes: Supabase product tables as canonical
  truth, a Mem0 retrieval layer for semantic recall, runtime consuming
  memories as context and never as source of truth.
- Section 15.3 names the earned-moment posture and cites OpenAI Codex
  Memories (idle-time background generation, redaction at write) as
  reference behavior; the idle digest adopts that capture pipeline while
  keeping storage authority with the user.
- Section 12.3 stays locked: assisted, not automatic. Every path in this
  lane ends in an explicit user confirmation before anything durable exists.
- Risk 3 (opaque memory users do not trust) motivates the visible retrieval
  step and in-chat controls; Risk 6 (privacy expectations rise with memory)
  shaped the embedder decision: the founder weighed egress against monolith
  compute and approved transit-only vectorization through Perplexity, with
  memory custody staying entirely in Argus infrastructure.

Competitive synthesis from the same conversation: Claude is search-first,
OpenAI is distillation-first, Argus is consent-first. This lane inherits
OpenAI's low-friction capture and Claude's transparent recall on top of the
provenance-and-receipts foundation neither competitor has.

Delivery mode note: this is a `normal_feature_branch` against the current
integration branch, not a new incubation lane. The condition that forced
incubation originally, no accepted current-base exposure control, no longer
holds once PR #386 is merged: the `ARGUS_ENABLE_PERSONALIZATION_MEMORY` flag
plus the admin/developer allowlist role gate are the accepted control
points, and everything here ships dark behind them.

## 2. Locked decisions

1. Scope is exactly five items, built in this order as slices: (1) history
   question answering, (2) Mem0 semantic recall, (3) idle-time proposal
   digest, (4) read/write private-chat split, (5) in-chat recall editing.
   Nothing else rides this lane.
2. S10 is absolute and unchanged: memory and chat history never enter the
   interpreter's input, influence routing, or touch any simulation
   parameter. Item 1 works only at answer composition, after interpretation
   and any simulation have completed.
3. History answering (item 1): when the interpreter's existing output
   classifies a turn as a question about the user's own prior decisions,
   ideas, runs, or memories, the answer surface composes from the existing
   omnisearch reader and `MemoryService.retrieve`. The UI shows a visible
   retrieval step (a "searching your saved decisions" state) before the
   answer, and every claim in the answer cites its source object (record,
   decision note, or run) with a tappable reference. If retrieval finds
   nothing, Argus says so plainly instead of guessing.
4. Mem0 (item 2), four parameters ratified: (a) index-only over confirmed
   records: `add()` at confirmation, `delete()` at delete, reset at reset,
   `search()` at retrieval; Mem0 never sees unconfirmed content and never
   holds storage authority; (b) embeddings run through Perplexity's
   embeddings API on the existing key; the founder approved memory text
   transiting Perplexity for vectorization on 2026-08-06, transit only:
   nothing is stored with the vendor, and vectors plus memories live only
   in our Supabase; (c) the vector store is pgvector in the existing
   Supabase database, no new datastore service; (d) Mem0 is the OSS
   library running in-process inside the API service; the hosted Mem0
   Platform is explicitly rejected because confirmed memories must stay in
   Argus custody.
5. Mem0 sits behind the existing `MemoryProvider` protocol with the
   fail-open semantics the persistence checkpoint built: provider down or
   erroring means canonical token-match fallback, never a failed turn and
   never a blocked control operation.
6. Idle digest (item 3): a background pass runs only after a conversation
   has been idle past a threshold, reads that conversation's messages
   transiently, and produces memory candidates through a new task in the
   existing OpenRouter task registry. Every candidate flows through the
   existing sensitivity assessor and policy gates (category allowlist,
   cooldowns, decline history). Candidates surface as proposals with the
   existing confirm/decline contract. Nothing is ever stored without
   confirmation, no transcript content persists beyond the typed candidate
   fields, and Mem0's extraction pipeline is not used for this.
7. The digest never runs for guests, never for conversations with the
   contribute opt-out set, and is bounded by the existing cost-ledger and
   allowance patterns with its own spend ceiling.
8. Private-chat split (item 4): two per-conversation controls replace the
   single toggle: "use memories here" (recall and history answers off) and
   "learn from this chat" (proposals and digest off). The existing
   `memory_opt_out` request field keeps meaning both-off for backward
   compatibility; granular fields are additive. Session state stays
   authoritative over storage exactly as PR #386 fixed it.
9. In-chat recall editing (item 5): recall notes and history answers carry
   chips (why stored, edit, delete) that route to the same canonical memory
   edit and delete contract as Data Controls, per the established
   conversational-edit macro pattern. No second edit path; in-chat edits get
   the same backend sensitivity re-assessment as modal edits.
10. All trust invariants from PR #386 carry unchanged: absolute guest denial
    before any memory code, flag plus admin/developer role exposure, no
    client sensitivity claims (422), backend-owned assessment failing
    closed, provenance and consent receipts on every record, no memory
    import, no auto-storage.
11. All user-facing copy ships in English and es-419 with no em dashes, and
    stored memory content remains verbatim user content, not localized.
12. Any file already at its modularity budget limit gets cohesive extraction
    rather than growth, matching the repo precedent.

## 3. Reserved / parked scope

- Automatic memory storage (OpenAI-style silent capture) -- parked until
  post-PMF usage data argues for revisiting the section 12.3 lock; the
  digest deliberately stops at proposals.
- Interpreter-detected "remember this" moments -- parked until digest
  acceptance data shows what explicit capture misses; needs
  interpreter-output taxonomy work that would bloat this lane.
- Memory import from other AI providers -- rejected, not just parked:
  imported blobs carry no provenance and no consent receipt, which breaks
  the trust model that differentiates Argus.
- Full incognito conversations (excluded from history, search, and memory)
  -- separate future lane; this lane's split covers the memory dimension
  only.
- Per-idea or per-project memory spaces, org-level controls and audit
  surfaces, cross-device sync of private-chat state -- all post-PMF
  questions.
- Memory-driven next-step suggestions beyond the recall note (Try next
  integration) -- parked; founder-deferred surface with its own spec debt.
- Mem0's extraction, dedup, and conflict-resolution pipeline -- explicitly
  unused; Argus owns extraction via its own task registry and owns storage
  via confirmation.
- Self-hosted embeddings -- parked as post-PMF privacy hardening: removes
  the last egress but puts model weight on the API service, which the
  current Render compute posture cannot spare. Unparks if Perplexity
  quality disappoints or the privacy bar rises.
- OpenAI embeddings -- considered only if Perplexity recall quality proves
  insufficient; a new vendor and key, so a founder decision either way.

## 4. Contract gates

- `docs/API_CONTRACT.md` section 17.2 -- history-answer payload contract,
  granular opt-out request fields, digest proposal surfacing, and any new
  problem codes.
- OpenAPI artifact regenerated; the sync suite enforces this.
- `docs/DATA_MODEL.md` -- digest bookkeeping state (idle tracking and digest
  receipts) if it needs durable shape; one forward migration maximum, and
  only for that bookkeeping.
- Environment contract, all four members learned in PR #386: `.env.example`,
  `render.yaml`, `ARGUS_RENDER_API_ENV` in `.github/argus-env.sh`, and
  `.github/private-alpha-release-profile.json` -- for every new variable
  (digest enable/ceiling, Mem0/pgvector configuration), declared off by
  default.
- Locale files `web/public/locales/{en,es-419}/common.json` for every new
  user-facing string.

## 5. Execution contract

- **PR shape:** one PR against the current integration branch, slices
  landing as ordered commits inside it (the shape that worked for PR #386).
  The implementation branch is cut fresh from the integration head only
  after the founder's current merge wave settles and PR #386 is merged.
- **Proof required before the PR counts as ready:**
  - Full `tests/memory/` suite plus new slice tests, including
    exploding-service guest-denial coverage for every new endpoint and
    request field, digest determinism under a fake clock, and Mem0
    integration tests that run hermetically against a fake provider.
  - An S10 proof for item 1: a test pinning that interpreter input bytes are
    identical with and without stored memories for the same turn.
  - Cross-commit flag-off byte-identity re-proof of the chat surface, same
    harness as PR #386.
  - Web suite green, production build green, ruff and modularity budget
    clean, environment-contract suites green.
  - Bilingual EN and es-419 browser QA with screenshots: history answer with
    its visible retrieval state, recall-note chips and in-chat edit, both
    split toggles, and a digest proposal being confirmed and declined.
  - Measured per-call cost for the digest task and the Perplexity embedding
    calls, reported in the PR body.
- **Where it stops:** a Ready PR with CI green and review threads answered.
  The founder merges. Applying the digest migration (if any) to hosted
  databases and flipping any new flags remain founder promotion decisions,
  never part of the PR landing.

## 6. Stop conditions

- If PR #386 is not merged into integration when this lane kicks off, stop
  and report; do not build on an unmerged base or attempt reconciliation.
- If item 1 cannot compose a history answer without feeding memory or chat
  history into interpreter input or routing, stop and report; do not bend
  S10 for answer quality.
- If Perplexity embeddings deliver poor recall quality or latency, stop and
  report; switching vendors or self-hosting is a founder decision, not a
  builder fallback.
- If the digest cannot produce useful candidates without persisting
  transcript content beyond typed candidate fields, or without exceeding
  its spend ceiling, stop and report.
- If any slice needs a durable table beyond digest bookkeeping, a change to
  guest, conversion, or handoff surfaces, or an `AccountCapabilities`
  field, stop and report.
- If a hosted-secret-shaped variable becomes necessary beyond the existing
  Perplexity key (any new external vendor or key), stop and report.
- If UI churn grows beyond the named surfaces (answer block with retrieval
  state, recall-note chips, header-menu toggles, digest proposal card),
  stop and report.

## Sources

### Argus authority

- `docs/PRODUCT.md` section 21 (decision filter).
- `docs/specs/private-alpha-next-decision-memo.md` sections 5.6, 12.3, 15.3,
  16.1, Memory privacy controls, Risk 3, Risk 6.
- `docs/specs/lanes/personalization-memory-contract.md` including the
  2026-08-05 addendum that locked Mem0 as the retrieval provider.
- PR #386 (`codex/personalization-memory-incubation-api-v1`, tip
  `017acd36`): the feature this lane builds on, including its QA evidence
  and the environment-contract lesson.

### External inspiration (researched 2026-08-06)

- https://support.claude.com/en/articles/11817273 -- chat search as visible
  RAG tool calls, categorized memory entries, incognito scope.
- https://learn.chatgpt.com/docs/customization/memories -- idle-time
  background memory generation, redaction at write, per-chat access and
  contribute controls, memory as secondary source.

### Inference

- The claim that history answering is the highest-value item rests on the
  PR #386 QA observation (correct memory shown under a "no record" answer),
  not on user data; digest acceptance rates and recall-note follow-up rates
  should be instrumented to test it.
