# Omnisearch is Argus's memory — conversation recall, asset rollups, and the actionable dossier

Status: **DELIVERED** — PR #306 merged into `codex/private-alpha-next` as
`b71f1eaf` on 2026-07-31. This document is retained as the accepted product
contract and historical implementation evidence; do not redispatch it as an
open lane.

Founder-locked 2026-07-29, after PR #305 (`88ab906d`) landed decision-first
previews. This spec is the shape that completes founder outcome 6
("Omnisearch lives up to its full capability") for the current product.

## 1. Why — the memory inspector of the moat

The decision memo defines the moat as the pre-trade intelligence layer plus
durable user memory, and lists what one-off chat agents lack — durable idea
objects, evidence dossiers, decision journal entries, and "a product-native
memory inspector." **Omnisearch is that memory inspector.** Memory you cannot
retrieve is not a moat. One sentence for the surface:

> Omnisearch is Argus's memory — search it, trust it, act from it.

The founder's recall story: a user with hundreds of conversations remembers
fuzzy context — "I talked about gold" or "I said these specific words" — not
titles. They search, recognize the conversation from their own words and
judgments, and land back in context in seconds.

## 2. Locked product decisions

1. **One row per conversation. Artifacts stay backend.** Search never
   explodes one conversation into per-artifact rows (the observed 5-rows-per-
   backtest failure, ~3M+1 rows for M runs). Artifacts feed the projection;
   they are not rows.
2. **Full-transcript haystack, object-first ranking.** The user's words
   mid-conversation become searchable (message-text index), but matches in
   durable objects (notes, decisions, evidence digests) rank above matches in
   raw chat text. Objects are the memory; chat is the residue. Archived
   conversations are included; deletions drop out by construction.
3. **The dossier panel** (hover/focus a conversation row) reads top to
   bottom as the conversation's memory, all deterministic, all existing
   canonical facts:
   - **Decision** — latest state + the note verbatim (quoted treatment,
     newlines preserved), attributed to the run it judged ("Watching · on
     monthly GLD buys") whenever the conversation holds multiple runs.
   - **What you tested** — bounded asset chips + strategy families + run
     count and date span.
   - **How it went** — the latest bounded outcome facts.
   - **Where you left off** — last finished run and date, with honesty
     nudges from stored truth only: an undecided last run ("you never
     decided on this"), an offered-but-untaken suggestion, a stale result
     ("from May").
   The matched fragment renders highlighted on the LEFT row (with a match
   count when several); the panel does not repeat it.
4. **Asset rollup row.** A query that resolves to a known asset shows one
   aggregate row above the conversations: "Your history with this asset" —
   runs involving it (a multi-asset run counts under each of its assets,
   labeled "involving"), decision counts by state, last-touched date. This is
   the decision memo's own Idea Ledger grouping ("by asset, strategy type,
   or theme") surfacing in search; asset first, same machinery extends to
   strategy type and theme later.
5. **Two panel verbs, each naming its run.** Both ride shipped contracts;
   nothing new is minted:
   - **Run it fresh** — the anchored run's exact setup with the window
     pulled to the present, submitted as a prebaked send (the Try next
     contract): opens the conversation and lands a Ready-to-run
     confirmation card through normal grounding. Never auto-executes.
   - **Change decision / Add decision** — the four states + note, through
     the existing decision API against the anchored run's evidence; chips
     and rows update immediately. Reads "Add decision" when the left-off
     nudge is an undecided run.
6. **Jump to match.** Opening from a matched row lands at the matched
   message, not the bottom of the conversation.
7. **Chips stay as decision filters** (founder-ratified): one keystroke to
   every conversation holding a decision in that state.
8. **Palette canon:** recents-first empty state, honest no-results state,
   keyboard-only completeness (Enter = open at match; Cmd+Enter = open at
   left-off; digits jump rows), as-you-type results with a debounce and a
   stated responsiveness bar at hundreds of conversations.
9. **Deterministic only.** Zero LLM/provider calls on hover, focus, search,
   preview, or either verb's composition. Exact + prefix matching stays the
   default; precision beats fuzzy for tickers and notes.

## 3. Reserved slots — sequenced by the decision memo, not built now

- **Compare** — the stack's next layer after decision memory is the
  comparison loop; the panel reserves the verb ("compare with my other gold
  tests") for that lane.
- **Shareable memo export** — the dossier is a proto pre-trade review
  artifact; export/share arrives as a button on this object later.
- **Semantic recall** — embeddings/graph retrieval wrap AROUND this same
  structure later (memo §5.6 sequence); the haystack contract must not
  preclude it.
- **Narrative recap** — a cached, off-path LLM-written arc remains parked
  under the previously recorded generation-gate doctrine.
- **Strategy-type and theme rollups** — same machinery as asset rollups.

## 4. Contract gates

- **#232 response-shape amendment**: grouping is server-side (client-side
  grouping splits lineages across cursor pages). The search response gains
  the conversation-recall row shape, the asset-rollup row shape, and match
  provenance (layer + message anchor). Ranking/cursor/ownership pins are
  updated deliberately, never silently.
- **Transcript index**: message-text search needs its own bounded index
  (migration gate) and must hold the #232 bounded-reads budget discipline;
  guest scope stays workspace-limited.
- **API_CONTRACT.md + OpenAPI + frontend types** for every typed addition.
- **No new durable recall model**: projections and indexes over existing
  truth only. A stored digest/summary object remains behind its own
  founder/schema gate.

## 5. Execution contract — one lane, one PR

Founder directive: this spec ships as **one PR that delivers the entire
spec**, base `codex/private-alpha-next`, built on this branch
(`claude/omnisearch-memory-recall`) with this spec as its first commit. The
"slices" below are the internal build order — **one commit per slice, never
separate PRs** — so review reads in layers while the product lands whole:

1. **Conversation rows + dossier projection** — collapse to one row per
   conversation server-side; conversation-level dossier assembled from the
   #305 decision projection (which becomes the "Your note" layer) plus run/
   evidence aggregation; left-off facts.
2. **Transcript haystack + jump-to-match** — message index (migration),
   object-first ranking, match provenance, open-at-message.
3. **Asset rollup row** — resolver-recognized queries get the aggregate row.
4. **Panel verbs + canon polish** — Run it fresh, Change/Add decision,
   keyboard depth, empty/no-results states, responsiveness bar.

Every commit keeps the full suite green (backend hermetic — move the
worktree `.env` aside for clean runs — plus web, ruff, modularity budget).
The PR is complete only with: EN/ES browser QA from a mock-auth memory-mode
stack with screenshots delivered to the founder (desktop and mobile),
API_CONTRACT/OpenAPI updated for every typed addition, labels applied
(enhancement, web, api, db), the Codex review round fixed with reasoned
replies and reactions, and CI green at the final tip. Stop at the posted PR;
the founder merges and closes the tracking issue.

## 6. Acceptance (condensed)

- One conversation with M backtests yields exactly one conversation row (plus
  an asset rollup when the query names an asset). No per-artifact rows.
- Words said only mid-chat are findable; a note/decision match outranks a
  chat-text match for the same conversation.
- The dossier renders decision (attributed), verbatim note, bounded tested/
  outcome facts, and a truthful left-off line with nudges — equivalently in
  Supabase and memory modes, EN/ES, desktop and mobile, zero LLM calls.
- Run it fresh lands a Ready-to-run card with the same setup on the current
  window and never auto-executes; Change/Add decision persists through the
  existing API and refreshes chips/rows/panel without stale state.
- Opening a matched row lands at the matched message.
- Chips filter conversations by decision state; empty query shows recents;
  no-results state guides the next attempt; keyboard-only journey works.
- The M+1 explosion is regression-pinned: existing #232/#252 contracts hold.

## 7. Stop conditions

Stop and report if any slice needs hover-time generation, a new durable
digest model, RAG/embeddings, raw-transcript rows in the response, or an
unbounded query per keystroke. Rollback per slice restores the prior surface
without touching canonical artifacts or notes.
