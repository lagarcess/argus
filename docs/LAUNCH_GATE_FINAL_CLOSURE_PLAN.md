# Launch Gate Final Closure Plan

This is the final launch-closure execution plan for Argus before private-user validation. It is not a new architecture plan and does not replace `docs/ARGUS_SYSTEM_STEERING.md`.

The steering layer is production-steerable. The remaining work is to close product-contract leaks, prove the browser loop, and make runtime behavior operationally consistent.

Do not reopen Tavily, Perplexity, SEC ingestion, transcripts, embeddings/RAG, personalization infrastructure, dashboards, onboarding expansion, mobile-first work, broad strategy expansion, or social mechanics during this closure pass.

## 1. Current Launch Status

Argus is materially hardened compared with the earlier runtime state.

- Tiered OpenRouter routing exists.
- Context packets exist.
- Route receipts exist.
- Replayability rules exist.
- Provider metadata is substantially improved.
- Semantic evals exist.
- The deterministic simulation truth layer is better separated from LLM-owned language.
- The browser loop has meaningful proof across messy prompts, reload, result follow-up, and recovery cases.

But the launch gate is not fully closed.

- Product-contract behavior still leaks in places.
- The chat can still sound too technical, flat, or report-like.
- Utility-tier behavior exists in code but is not fully operationally proven.
- Sidebar titles can remain `New idea` after meaningful conversation.
- Authoritative runtime-path closure is not fully proven.
- Browser proof exists, but final transcript evidence must explicitly cover titles, runtime continuity, recovery, and conversational feel.

The remaining risk is no longer core engine architecture. It is user trust, product polish, and operational consistency.

## 2. Remaining Launch Risks

The final launch risks are:

- Product-contract leaks where a capability exists but the user-visible behavior does not reliably happen.
- "Tier exists, behavior unproven" gaps, especially utility-tier naming.
- Sidebar/title quality and persistence gaps that make Recents feel unfinished.
- Dense "financial report" tone in explanations, follow-ups, and recovery.
- Incomplete final browser-proof evidence across the whole matrix.
- Dual runtime-path risk from compatibility surfaces and legacy routes.
- Oversized router ownership risk in `src/argus/api/routers/agent.py`.
- Incomplete operational enforcement for cache, TTL, freshness, and stale context behavior.

Launch closure should treat these as contract issues, not polish trivia. Titles, reload state, result actions, recovery, and tone affect whether private users trust the product enough to return.

## 3. Product-Contract Closure

Every important runtime capability must become operationally observable.

Utility-tier behaviors are part of the product contract. They are not optional decoration when the UI depends on them for recall, continuity, and trust.

Fail-open background polish is acceptable only when it is observable and recoverable:

- The primary chat path must not be blocked by title generation.
- A failed title task must be visible internally through route receipts or structured logs.
- The user should never be stuck with stale placeholder state after a meaningful turn without the failure being diagnosable.

Conversation titles should become first-class runtime artifacts:

- Generate after the first meaningful turn or first completed run.
- Use the Tier 1 utility model.
- Persist `title` and `title_source=ai_generated`.
- Emit a `title` SSE event or guarantee persistence before post-turn history refresh.
- Write a route receipt for the title-generation task.
- Remain fail-open but observable.
- Never overwrite `title_source=user_renamed`.
- Never block the primary runtime path unless the product explicitly makes title generation launch-critical.

Acceptance criteria:

- Sidebar Recents should not remain `New idea` after meaningful interaction.
- Generated titles survive refresh and reload.
- Generated titles cover exploratory, educational, unsupported, and strategy conversations.
- Title fallback is observable internally.
- Title generation does not run before the canonical `final` SSE frame.
- A failed title generation task does not break chat completion.

## 4. Response Quality Closure

Argus should feel:

- Grounded.
- Practical.
- Conversational.
- Calm.
- Curiosity-forward.
- Trustworthy.

Argus should not feel:

- Theatrical.
- Robotic.
- Verbose.
- Like a financial PDF.
- Like a generic AI assistant.

Final response-quality rules:

- Use short paragraphs.
- Use scannable formatting.
- Explain assumptions simply.
- Preserve caveats without sounding legalistic.
- Avoid unsupported causality.
- Avoid unsupported investment advice.
- Optimize for clarity, trust, and forward momentum.
- Do not chase perfect prose at the expense of groundedness or speed.

Ownership boundary:

- LLMs own natural language, clarification, education, summaries, and curiosity-forward continuation.
- Deterministic systems own facts, validation, IDs, state transitions, replayability, provider truth, persistence, and recovery guarantees.

Acceptance criteria:

- Result summaries and follow-ups sound like a helpful investing lab partner, not a report.
- Unsupported ideas redirect into nearby testable ideas without scolding the user.
- Caveats are present but light.
- Browser transcripts judge readability and conversational feel, not just correctness.

## 5. Runtime-Path Closure

Final runtime closure tasks:

- Decide `/internal/agent-runtime/turn`: remove it, gate it, or explicitly mark it test-only.
- Keep one authoritative launch runtime path.
- Keep `chat_service.py` compatibility-only or retire it.
- Prevent new production imports from `argus.api.chat_service`.
- Thin `src/argus/api/routers/agent.py` only where it directly reduces launch-loop brittleness or duplicate-runtime risk.
- Keep router ownership limited to auth, request validation, transport/SSE shape, persistence boundary, and error shaping.

No additional runtime brains, fallback systems, orchestration paths, or persistence paths are allowed before launch.

Do not refactor for architecture purity. Refactor only when it reduces launch-loop risk.

## 6. Browser Acceptance Closure

Final browser QA is the acceptance gate. More refactoring is lower value than proving the product loop in the browser.

Required transcript matrix:

- Messy beginner prompts.
- Partial strategy prompts.
- Unsupported prompts.
- Contradictory prompts.
- Reload and recovery behavior.
- Title generation behavior.
- Next-experiment continuity.
- "Why did this happen?" follow-ups.
- Failed provider/model paths.

Each transcript must judge:

- Groundedness.
- Readability.
- Trust.
- Continuity.
- Recovery.
- No unsupported causality.
- No unsupported advice.
- Conversational feel.

Evidence requirements:

- Store transcripts under `temp/`.
- Include conversation ids and prompts.
- Note any route receipt/fallback evidence where relevant.
- Do not call browser acceptance passed until title behavior, reload behavior, result actions, and recovery have all been observed in the browser.

## 7. Cache/Freshness Operational Closure

Keep cache and freshness work small and practical.

Implement only:

- Minimum operational freshness enforcement.
- Context packet immutability once attached.
- Replay-safe packet attachment.
- Practical TTL handling by provider/fact type.
- Stale packet marking or replacement through new packets, not mutation of completed explanations.

Do not build:

- Distributed cache systems.
- Generalized retrieval infrastructure.
- Large observability systems.
- Broad market-feed behavior.

Operational rules:

- Cache must not become simulation truth.
- Historical closed OHLCV may live longer than recent windows.
- FRED macro packets may be longer-lived after release.
- Alpaca news stays short-lived, scoped, and capped.
- Corporate actions use medium freshness by symbol/date range.
- Movers/most actives remain very short-lived and narrow context only.
- Freeform LLM chat should not be broadly cached.

## 8. CI / Operational Proof

No launch-gate item is complete unless it is operationally proven.

Required proof:

- Backend tests.
- Focused runtime suites.
- Frontend tests.
- Frontend lint.
- Frontend production build.
- Browser transcript evidence.
- CI proof or explicit local-only caveat.

Minimum local commands:

- `NUMBA_DISABLE_JIT=1 poetry run pytest -q`
- `poetry run ruff check src tests`
- `cd web && bun test`
- `cd web && bun run lint`
- `cd web && bun run build`

If CI is unavailable or not run, the closure report must say so plainly.

## 9. Final Closure Checklist

- [ ] Response-quality contract is applied to chat, clarification, result summaries, breakdowns, follow-ups, and safe recovery.
- [ ] Utility-tier title flow is browser-proven.
- [ ] Conversation titles persist with `title_source=ai_generated`.
- [ ] Sidebar Recents no longer remain `New idea` after meaningful interaction.
- [ ] Title fallback/failure is observable internally.
- [ ] One authoritative launch runtime path is documented and guarded.
- [ ] `/internal/agent-runtime/turn` is removed, gated, or explicitly test-only.
- [ ] `chat_service.py` is compatibility-only or retired.
- [ ] No new production code imports `argus.api.chat_service`.
- [ ] Browser transcript matrix is complete.
- [ ] CI proof exists, or local-only caveat is explicit.
- [ ] Replayability remains intact from persisted run facts plus attached context packet references.
- [ ] Route receipts include task, tier, model, fallback, latency, outcome, token usage when available, and context packet ids when available.
- [ ] Tier 4 remains grounded in engine facts plus structured context packets.
- [ ] Reload and recovery continuity are browser-proven.
- [ ] Saved result actions work after refresh.
- [ ] Unsupported requests redirect into nearby testable ideas.
- [ ] No unsupported causality or investment advice appears in browser transcripts.

## 10. Stop Condition

Once this closure plan is complete, stop planning and begin private-user validation.

At that point, real users provide more valuable information than additional architectural refinement.

## Anti-Patterns And Drift Alarms

Avoid these mistakes during final closure:

- Do not use regex or phrase gates for natural-language understanding, tone enforcement, signal repair, or QA gate passing.
- Do not patch just to make a gate pass. Fix the macro pattern that made the gate fail.
- Do not loosen tests to hide broken behavior. Relax exact wording only where language is LLM-owned.
- Do not create another chat brain, fallback stack, or orchestration path.
- Do not route new behavior through `chat_service.py`.
- Do not make the frontend infer runtime truth from prose.
- Do not let deterministic fallback copy become the normal assistant voice.
- Do not make context packets alter simulation truth.
- Do not let refreshed context rewrite completed explanations.
- Do not optimize model choice before route receipts and eval evidence exist.
- Do not expand providers, dashboards, strategy breadth, onboarding, or personalization before browser-loop closure.
- Do not keep planning once the browser proof is the next risk reducer.

You are drifting if:

- A fix depends on a keyword list for what a user "probably means."
- A test passes only because an exact assistant sentence was changed.
- A user-facing behavior exists in code but has no browser transcript.
- A fallback silently changes model class, reliability, or product behavior.
- A title, result, route receipt, or context packet can be lost on refresh without evidence.
- The router starts owning conversation decisions instead of transport and boundaries.
- A module is changed for cleanliness but no launch risk is reduced.
- The product starts feeling like a report, dashboard, or generic finance assistant instead of a chat-first experimentation system.
