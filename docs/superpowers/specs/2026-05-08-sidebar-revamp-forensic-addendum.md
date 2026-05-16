# Sidebar Revamp Forensic Addendum

Date: 2026-05-08
Status: Read-only forensic handoff for fresh agent review
Baseline: PR 80 / `main` commit `091b226` (`[codex] Complete conversation continuity gap plan (#80)`)
Current branch observed: `codex/sidebar-revamp`

## TL;DR

The sidebar revamp direction is product-aligned, but the implementation attempt crossed into PR 80's protected conversational runtime and chat-continuity surface.

PR 80 intentionally made the live conversation the primary product surface. It established that:

- `/api/v1/chat/stream` must deliver canonical SSE events through `final` and `[DONE]`.
- `final` is the decisive UI event that renders confirmation cards, result cards, result actions, and persisted message ids.
- `web/components/chat/ChatInterface.tsx` owns the visible chat product moment.
- Reload/navigation must hydrate persisted `messages.metadata` back into structured confirmation cards, result cards, latest run ids, and result actions.
- Runtime state belongs to LangGraph checkpointer; Supabase stores durable product records.

The sidebar work should have wrapped around this. Instead, it edited through it:

- Live chat SSE was modified to generate AI titles before yielding `final`.
- Chat card hydration was moved out of `ChatInterface.tsx` into a reusable helper for search preview.
- Frontend static tests were changed to accept that move, weakening the PR 80 guard.
- A runtime extraction file and runtime state-machine test were modified despite not being sidebar work.

The safest recovery is to preserve the sidebar concept, but restart implementation from PR 80/main with explicit guardrails: do not modify live chat streaming, runtime extraction, or PR80 card hydration unless a separate approved chat-runtime plan requires it.

## PR 80 Intent And Protected Boundaries

PR 80 was a conversation-continuity milestone. Its intent was not just UI polish; it defined the product-critical behavior that makes Argus feel like a trustworthy chat-first investing assistant.

Relevant source-of-truth principles:

- `docs/CONVERSATIONAL_RUNTIME.md`: reloading or navigating away from chat must hydrate visible messages and structured UI artifacts, including confirmation cards, result cards, latest run ids, and available actions.
- `docs/CONVERSATIONAL_RUNTIME.md`: result cards render before the summary and own the save-strategy control.
- `docs/PRODUCT.md`: the chat result card owns Save Strategy because saved strategies must come from real completed result state, not reconstructed frontend prose.
- `docs/ARCHITECTURE.md`: LangGraph owns runtime state; Supabase owns durable product persistence.
- `docs/API_CONTRACT.md`: canonical streaming is data-only SSE with `stage_start`, `token`, `stage_outcome`, `final`, then `[DONE]`.

Protected boundaries for future sidebar work:

- Do not modify `src/argus/agent_runtime/**` for sidebar changes.
- Do not modify live chat streaming behavior in `src/argus/api/routers/agent.py` except through a dedicated chat-runtime plan.
- Do not put any new feature work between persisted assistant message creation and the canonical `final` SSE frame.
- Do not move or weaken persisted card hydration from the main chat path without an explicit refactor plan and equivalent regression tests.
- Do not alter backtest state-machine tests to accommodate sidebar changes.

## What Went Wrong In The Sidebar Spec Attempt

The sidebar spec had the right product direction but was underconstrained around sacred chat-runtime boundaries.

The product direction that was sound:

- Make Recents a chat-first resume surface.
- Replace stale sidebar search with a focused search overlay.
- Display chats as canonical search results while allowing strategy/run content to explain why a chat matched.
- Move settings/profile/feedback into lower-friction overlays.
- Generate useful chat titles so users do not see dozens of `New idea` rows.
- Add guarded feedback attachments.
- Fix collapsed-sidebar icon flicker.

The specification gaps that created implementation risk:

1. `Split sidebar concerns out of ChatInterface.tsx`

This was too broad. It gave permission to move PR80 chat hydration logic. The safe wording should have been:

> Extract sidebar shell/nav/profile/search-launch concerns only. Do not move live chat streaming, persisted message hydration, confirmation/result card hydration, or result action logic.

2. `Expanded Search preview renders scrollable actual chat history`

This is product-correct, but it did not define the implementation boundary. The attempt reused live chat hydration. The safer wording:

> Search preview may render persisted message metadata through a search-only adapter. It must not become a dependency of the live chat surface, and it must not move chat hydration out of `ChatInterface.tsx`.

3. `Generate useful AI chat titles`

This is necessary for search and Recents, but the spec did not say title generation is non-critical-path. The safer wording:

> AI title generation is a recall enhancement. It must never block, delay, or replace the current turn's `final` SSE event. It must never prevent confirmation/result card rendering.

4. `Backend/API work must remain contract-first`

Correct, but too broad. It failed to distinguish new search/feedback contracts from protected chat stream contract. Safer wording:

> Search and feedback contracts may evolve in this pass. The live chat stream contract must remain unchanged unless separately approved.

5. Test plan did not protect PR80 enough

The test plan added title/search/feedback checks but did not require:

- `final` always reaches the frontend even if title generation fails.
- Confirmation cards render from final payload.
- Result cards render from final payload.
- Reload hydrates confirmation/result cards and result actions from metadata.
- Search preview implementation does not alter `ChatInterface.tsx` card hydration.

## AI Title Generation Clarification

AI title generation should not mean titles only appear after a strategy exists.

It should generate after the first meaningful conversational turn, even if the chat is educational or exploratory:

- "Explain drawdown" can become `Understanding Drawdown`.
- "I am new to investing" can become `Investing Basics Starter`.
- "What if I bought Tesla after drops?" can become `Tesla Dip Strategy`.

The rule is about stream safety, not title scope:

- Generate titles for non-strategy chats too.
- Never overwrite `title_source = user_renamed`.
- Never put naming between the assistant turn and the `final` event.
- Prefer post-final or background title generation.
- If title generation fails, the chat turn must still complete normally.

## Forensic Matrix

| File | Main / PR80 intention | What changed | Why it was touched | Alignment with principles | Sidebar-required | Risk to chat continuity | Recommendation |
|---|---|---|---|---|---|---|---|
| `.gitignore` | Ignore local/dev artifacts | Added `.superpowers/` | Avoid local skill/session noise | Fine | No | None | Keep |
| `docs/superpowers/specs/2026-05-08-sidebar-revamp-design.md` | Did not exist | Added sidebar revamp design spec | Capture approved sidebar direction | Product direction mostly aligned, but underconstrained | Yes | Medium as written | Rewrite before reimplementation |
| `docs/API_CONTRACT.md` | Preserve PR80 chat/SSE/card contract and existing search/feedback contract | Added chat-only search, preview metadata, feedback attachments, nested title event shape | Contract-first implementation of sidebar search/feedback/title work | Search/feedback aligned; title stream shape/order needs caution | Partial | Medium | Rework with explicit protected chat stream boundary |
| `docs/DATA_MODEL.md` | Persistence truth for conversations/messages/runs/feedback | Added title-source rules, attachment metadata, deleted recovery notes | Support AI titles, feedback uploads, archived/deleted semantics | Mostly aligned | Partial | Low | Keep or lightly rework |
| `docs/api/openapi.yaml` | Public API schema sketch | Added search schemas and feedback attachment route | Support new contract | Aligned if API shape survives | Partial | Low | Rework after final API decision |
| `src/argus/agent_runtime/extraction/structured.py` | Runtime extraction and deterministic guardrail path | Added compatibility alias for a resolver test | Test compatibility while working nearby | Not aligned with sidebar scope | No | High | Revert |
| `src/argus/api/chat_service.py` | PR80 runtime helper boundary for result cards, onboarding, persistence helpers | Added `maybe_generate_conversation_title` | AI chat title generation | Goal aligned, placement risky | Indirect | High | Rework outside critical stream path |
| `src/argus/api/routers/agent.py` | Canonical live chat SSE route | Calls title generation before yielding `final`; emits title event shape | Update title live in UI | Violates critical-path safety | Indirect | Critical | Revert or rework first |
| `src/argus/api/routers/feedback.py` | Simple JSON feedback endpoint | Added multipart guarded attachment upload | Structured bug report attachments | Aligned | Feedback only | Low-medium | Keep after security review |
| `src/argus/api/routers/search.py` | Mixed global search over chats, strategies, collections, runs | Rewritten as chat-only display with strategy/run folded into containing chat and preview messages | New omni-search vision | Product-aligned but broad/in-memory style may be inefficient | Yes | Medium | Rework for performance and separation |
| `src/argus/api/schemas.py` | Shared API models | Search item now chat-only; added preview messages, metadata, status, attachment models, `deleted_at` patch | Search/feedback/profile data support | Mostly aligned | Yes | Medium | Rework with final contract |
| `src/argus/domain/supabase_gateway.py` | Supabase query/persistence gateway | Search fetches conversations/messages/strategies/runs broadly; added storage upload | Search preview and feedback uploads | Upload aligned; search broadness questionable | Yes | Medium-high | Rework search; keep upload if reviewed |
| `tests/test_alpha_api.py` | Backend alpha regression tests, including search and chat stream | Replaced mixed search test; added title/search/upload tests | Cover new behavior | Some useful tests, missing title-does-not-block-final | Partial | Medium | Rework |
| `tests/test_alpha_api_supabase.py` | Supabase integration tests | Updated search mock expectations to chat-only preview | Cover new search shape | Aligned with search direction | Partial | Low-medium | Rework |
| `tests/test_backtest_state_machine.py` | Core runtime state-machine regression | Relaxed comparison around `resolution_provenance` | Unclear compatibility fix | Not sidebar-related | No | High | Revert or investigate separately |
| `web/__tests__/alpha-frontend.test.ts` | Frontend static guard for PR80 chat continuity | Updated tests to accept hydration move into `messageHydration.ts`; added sidebar static checks | Keep tests passing after refactor | Weakens chat-boundary protection | Partial | High | Rework |
| `web/app/globals.css` | Global styles and animations | Added sidebar icon outline animation | Collapsed icon hover animation | Aligned | Yes | Low | Keep |
| `web/bun.lock` | Dependency lockfile | Added `html2canvas` | Screenshot attachment capture | Aligned if feedback upload stays | Feedback only | Low | Keep if feature stays |
| `web/package.json` | Web dependency manifest | Added `html2canvas` | Screenshot attachment capture | Aligned if feedback upload stays | Feedback only | Low | Keep if feature stays |
| `web/components/chat/ChatInterface.tsx` | Primary conversation product surface; live stream UI; persisted card hydration; sidebar shell | Removed inline hydration, removed lower search/settings, added search/profile/recents wiring | Sidebar implementation and search reuse | Direction mixed; crossed protected chat boundary | Partial | Critical | Rework from main outward |
| `web/components/chat/messageHydration.ts` | Did not exist | Extracted PR80 hydration logic from `ChatInterface.tsx` | Reuse for search preview | Useful abstraction in theory, wrong scope now | No | High | Revert or replace with search-only adapter |
| `web/components/sidebar/ChatSearchOverlay.tsx` | Did not exist | New omni-search overlay; imports chat hydration and card components | Search overlay implementation | Product-aligned, but coupled to live chat hydration | Yes | Medium | Rework and decouple |
| `web/components/sidebar/ProfileMenu.tsx` | Did not exist | New portal profile/settings/data/feedback overlays | Settings migration | Direction aligned, needs polish and i18n | Yes | Low-medium | Rework polish |
| `web/components/sidebar/SidebarNavButton.tsx` | Did not exist | Stable nav icon slot and tooltip behavior | Collapse flicker and icon animation | Aligned | Yes | Low | Keep |
| `web/components/sidebar/RenameChatDialog.tsx` | Did not exist | Native rename modal | Replace browser prompt | Direction aligned, needs i18n/focus polish | Yes | Low-medium | Rework polish |
| `web/components/feedback/FeedbackDialog.tsx` | Simple feedback/rating dialog | Structured bug form, uploads, screenshot | Upgrade Report a Bug | Aligned, but hardcoded copy and visual polish issues | Feedback only | Low-medium | Rework polish |
| `web/lib/argus-api.ts` | API client and chat stream parser | Search type changed, FormData support, nested title parser, upload endpoint | Support new contracts | FormData good; title/search changes need final decision | Partial | Medium | Rework |
| `web/public/locales/en/common.json` | English strings | Chat-only Recents empty copy | Match Recents chat-only behavior | Aligned | Yes | Low | Keep |
| `web/public/locales/es-419/common.json` | Spanish strings | Chat-only Recents empty copy | Match Recents chat-only behavior | Aligned | Yes | Low | Keep |

## Suggested Next Steps For Discussion

### Option A: Stash And Restart From Main

Process:

1. Stash all current uncommitted sidebar work.
2. Return to PR80/main.
3. Verify golden-path chat manually and with tests.
4. Rewrite the sidebar spec with protected-boundary language.
5. Reimplement in narrow slices.

Pros:

- Safest for product trust.
- Guarantees PR80 conversational behavior remains intact.
- Forces cleaner implementation boundaries.
- Easiest to reason about in review.

Cons:

- Some salvageable work must be re-applied manually.
- Slower in the short term.

Best when:

- The live chat regression is confirmed or trust in the current branch is low.

### Option B: Surgical Revert Of Critical Files Only

Process:

1. Revert `src/argus/api/routers/agent.py`, `src/argus/api/chat_service.py`, `src/argus/agent_runtime/extraction/structured.py`, `tests/test_backtest_state_machine.py`, and `web/components/chat/ChatInterface.tsx` to main.
2. Delete or decouple `web/components/chat/messageHydration.ts`.
3. Keep lower-risk sidebar, feedback, docs, and search files for further review.

Pros:

- Preserves more implementation work.
- Faster if the team wants to salvage current branch.

Cons:

- Still leaves a branch with broad API/search/frontend changes.
- Higher chance of hidden coupling.
- Requires careful follow-up audit after revert.

Best when:

- The team wants to save time and is willing to test heavily.

### Option C: Full Forensic Debug Before Any Revert

Process:

1. Keep current branch as evidence.
2. Reproduce the live chat regression.
3. Trace stream events and UI state transitions.
4. Identify exact failing boundary.
5. Decide revert scope from evidence.

Pros:

- Most scientifically precise.
- Could reveal a smaller root cause.

Cons:

- Slower.
- The branch is already scope-contaminated; root cause may not be singular.

Best when:

- The team needs to understand the regression mechanism before choosing rollback.

## Recommended Approach

Recommended: Option A or a hybrid of A and B.

Best practical path:

1. Preserve current branch as evidence.
2. Create a clean branch from PR80/main.
3. Rewrite the sidebar spec first with hard protected-boundary language.
4. Reimplement in this order:
   - Sidebar nav button and icon animation only.
   - Profile button/menu shell only.
   - Recents label/chevron split with chat-only dropdown.
   - Search overlay UI using a search-only preview adapter.
   - Backend search contract and implementation.
   - Feedback uploads.
   - AI title generation as post-final/background work.
5. After each slice, run PR80 golden-path chat tests.

## Guardrails For The Fresh Agent

Before editing:

- Read `docs/PRODUCT.md`.
- Read `docs/ARCHITECTURE.md`.
- Read `docs/API_CONTRACT.md`.
- Read `docs/DATA_MODEL.md`.
- Read `.agent/designs/argus/DESIGN.md`.
- Read `docs/CONVERSATIONAL_RUNTIME.md`.
- Read this addendum.

Do not edit in the first pass:

- `src/argus/agent_runtime/**`
- `tests/test_backtest_state_machine.py`
- Live chat SSE in `src/argus/api/routers/agent.py`
- Chat card hydration in `web/components/chat/ChatInterface.tsx`

Unless separately approved, sidebar work may edit:

- Sidebar-only frontend components.
- Search-specific frontend components.
- Search API/router/schema/docs.
- Feedback dialog/router/schema/docs.
- Locale strings.
- CSS for sidebar-specific animation.

Required regression checks after any implementation:

- A normal chat turn reaches `final` and `[DONE]`.
- A confirmation turn renders a confirmation card.
- An approved backtest renders a result card.
- Result card actions still include result context.
- Reload hydrates confirmation/result cards from message metadata.
- AI title failure cannot prevent `final`.
- Search preview does not require moving live chat hydration out of the chat surface.

## Proposed Rewrite Of The Risky Spec Clauses

Replace:

> Split sidebar concerns out of `web/components/chat/ChatInterface.tsx`.

With:

> Extract sidebar shell concerns only. Do not move or modify live chat streaming, message hydration, confirmation/result card rendering, or result action hydration in `ChatInterface.tsx` during this pass.

Replace:

> Search preview must provide enough message history to render the expanded panel without the frontend inventing content.

With:

> Search preview must render persisted message content and metadata through a search-only adapter. The live chat hydration path must remain untouched.

Replace:

> Generate useful AI chat titles so search is meaningful.

With:

> Generate useful AI chat titles after meaningful turns, including educational and exploratory chats, but only outside the critical stream path. Title generation must never block or precede the canonical `final` event.

Replace:

> Backend/API work must remain contract-first and thin-router aligned.

With:

> Search and feedback API changes must be contract-first. The live chat stream contract is protected and must remain unchanged in this sidebar pass.

