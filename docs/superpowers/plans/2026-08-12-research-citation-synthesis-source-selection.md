# Research Citation, Synthesis, and Source Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to execute this plan.

**Goal:** Close issues #451, #457, and #407 in one research-runtime lane so narrative company questions use a publisher-capable tier, market surveys either name verified assets or state the precise synthesis failure, and the sources drawer contains only period-plausible, publisher-unique evidence.

**Architecture:** Keep the LLM classifier as the multilingual semantic owner and add typed fields for publisher-evidence need and the earliest date implied by the question. Enforce those facts at the existing research dispatch/composition boundary, retain a bounded internal citation pool, and perform freshness plus publisher selection immediately before the one typed sources sidecar is built. Keep provider hosts blocked, leave the drawer unchanged, and keep the missing-subject rule local to research synthesis so the parallel #453 chat-recovery lane owns no shared helper.

**Tech Stack:** Python 3.10, Pydantic, Perplexity Agent API adapter, LangGraph stage composition, pytest, Playwright, GitHub Actions.

## Global Constraints

- Work only on `codex/issues-451-457-407-research-trust`, based on `origin/codex/private-alpha-next` at `8025672924d1c74eb80cc926c72b5d8574b613d7`.
- Treat `docs/superpowers/specs/2026-08-07-research-to-test-rail.md` and the founder's issue evidence as the locked product contract.
- Never unblock `perplexity.ai` or another provider-owned host in `PROVIDER_HOSTS`.
- Never add regex, localized phrase tables, or a second router before the LLM interpreter.
- Do not edit `render.yaml`, `.env.example`, `.github/argus-env.sh`, the release profile, `.env`, `web/.env.local`, either locale catalog, or the parallel #453 chat-recovery owners.
- Preserve the existing typed sources drawer and the research sidecar builder as the only public output boundaries.
- Exact-head acceptance requires English and es-419 browser proof for a narrative fundamentals question and a market-movers question.
- Stop before merge, deploy, hosted configuration changes, or issue closure.

### Task 1: Lock narrative routing and publisher-source requirements

**Files:**
- Modify: `tests/research/test_research_answer.py`
- Modify: `tests/research/test_research_sources_and_voice.py`
- Modify: `src/argus/agent_runtime/research_answer.py`
- Modify: `src/argus/agent_runtime/research_grounded.py`

- [x] Add failing tests proving a pure live quote still uses `fast`, while a typed narrative clause can never use `fast` and sends the balanced publisher-capable tool set.
- [x] Add a failing test proving a company fundamentals answer cannot publish claim prose when no public publisher source survives.
- [x] Extend `ResearchQueryExtraction` with typed publisher-evidence need and an ISO question-period start. Update classifier guidance so explanatory clauses in any language are company/narrative reads, not live quotes.
- [x] Add the deterministic post-classification shape guard and publisher-source fail-closed behavior without naming tools in user prose.
- [x] Run focused tests and require green:

```bash
poetry run pytest tests/research/test_research_answer.py tests/research/test_research_sources_and_voice.py -q --no-cov
```

### Task 2: Select period-plausible, publisher-unique sources

**Files:**
- Create: `src/argus/domain/research/source_selection.py`
- Create: `tests/research/test_research_source_selection.py`
- Modify: `src/argus/domain/research/contracts.py`
- Modify: `src/argus/domain/research/perplexity_agent.py`
- Modify: `src/argus/agent_runtime/research_grounded.py`
- Modify: `tests/research/test_research_citations.py`

- [x] Add failing tests proving an explicitly stale dated page is omitted for a `today` market pulse, an undated page remains eligible, duplicate publisher pages collapse to one, and five distinct publishers survive even when one outlet arrived first.
- [x] Add a failing parser test proving the provider packet retains enough bounded citations for selection after the first five arrivals.
- [x] Retain a bounded internal source pool, then select at the shared typed-sidecar boundary using the question's typed period. For `market_pulse`, use the server's question date when the classifier supplied no bound.
- [x] Keep exact-URL sanitization and provider-host filtering unchanged, cap the public drawer at five after publisher deduplication, and apply the same selector to cached, inline, and background-completed packets.
- [x] Run focused tests and require green:

```bash
poetry run pytest tests/research/test_research_source_selection.py tests/research/test_research_citations.py tests/research/test_research_client.py -q --no-cov
```

### Task 3: Make survey synthesis truthful when the subject is absent

**Files:**
- Modify: `tests/research/test_research_shapes.py`
- Modify: `tests/research/test_research_sources_and_voice.py`
- Modify: `src/argus/agent_runtime/research_grounded.py`

- [x] Add failing English and es-419 tests for a market survey that used web retrieval and returned sources but no verified mover. Require one precise synthesis-failure sentence, no subjectless figure/asset hedge, no next-experiment rows, and the typed degraded code.
- [x] Add a failing test proving web or URL retrieval counts as grounding even when `finance_search` did not run.
- [x] Replace the survey answer only when no resolver-verified subject is concretely present in the answer. Distinguish no retrieval from retrieval-without-synthesis and render only copy whose typed subject exists.
- [x] Preserve successful mover answers and runnable rows when the provider names a resolver-verified asset.
- [x] Run the focused shape suite and require green:

```bash
poetry run pytest tests/research/test_research_shapes.py tests/research/test_research_sources_and_voice.py -q --no-cov
```

### Task 4: Update the contract and run deterministic verification

**Files:**
- Modify: `docs/API_CONTRACT.md`
- Verify: `tests/research/`
- Verify: `tests/test_research_job_reconciliation.py`
- Verify: `scripts/check_modularity_budget.py`

- [x] Update the research-response contract with narrative tier selection, fail-closed publisher evidence, subject-complete survey recovery, period plausibility, and publisher deduplication.
- [x] Run the complete research suite:

```bash
poetry run pytest tests/research -q --no-cov
```

- [x] Run the focused runtime integration, structural source-boundary tests, formatting, static checks, and modularity budget required by the repository.
- [x] Inspect the diff for forbidden files, provider-host relaxation, user-facing em dashes, and semantic overlap with #453.

### Task 5: Capture exact-head bilingual browser acceptance

**Files:**
- Create: `docs/reports/evidence/451-457-407/README.md`
- Create: durable browser screenshots and sanitized turn receipts under `docs/reports/evidence/451-457-407/`

- [x] Drive English and es-419 narrative fundamentals turns through the real browser/API path and prove each answer carries at least one public publisher source.
- [x] Drive English and es-419 market-movers turns and prove each answer either names verified movers or gives the precise synthesis failure.
- [x] Inspect every displayed source's URL, publisher, and date against the asked period. Record the exact commit SHA and avoid storing credentials or private user data.
- [ ] Re-run affected acceptance if any later code change moves the head.

### Task 6: Reconcile, publish, and exhaust review

- [ ] Fetch `origin/codex/private-alpha-next`, record its current SHA, compare semantic overlap, and merge it one-way if it advanced. Never rebase the evidenced branch.
- [ ] Run the merged-tree modularity budget and all affected exact-head checks after reconciliation.
- [ ] Commit with Conventional Commits, push the worker branch, and open a ready PR against `codex/private-alpha-next` with issues #451, #457, and #407 linked and existing labels applied.
- [ ] Wait for terminal CI, request Codex review only on the exact green head, resolve every actionable thread proportionally, and repeat only for the latest fix delta until one clean pass and zero unresolved threads.
- [ ] Report the original integration base, current integration SHA, reconciliation SHA if any, overlap disposition, retained/invalidated evidence, exact PR head, terminal CI, clean review verdict, and stop.
