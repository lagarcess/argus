# Cuadrao Business lane: handoff (paused October 9, 2026)

**Status: paused by the founder.** Claude usage is reserved for the Consumer lane. This document and the GitHub records it links let another agent resume. No private notes, chat transcripts or scratch folders are needed.

**Update, October 10, 2026 (America/Chicago).** The product-direction discussion took place. The founder approved the Business agent direction. The [Business agent execution spec](../specs/lanes/cuadrao-business-agent-execution-spec.md) now owns the Business build order. These holds change:
- The hold on new product work is lifted for the work in that spec.
- "Business chat stays off" is lifted. Business chat is the agent's surface, so the agent needs it on. Build it now. It turns on in hosted environments for pilot businesses, through server flags, after J1 passes and the founder approves.
- Live calls, the spend limit, deployment, hosted migration, activation and merges stay held. The spec lists the open spend-limit decision (F6).

**Founder holds, in force:**
- New product work and E0 are on hold.
- The founder is reassessing the Business pilot after an interview with an accounting firm. **No new roadmap is approved.** That interview is not recorded in the repository, and the successor must not infer its content.
- Business stays off. **Business chat stays off.**
- AI tests have an approved **hard $5.00 total cap**, but **no live calls are authorized yet**.
- No deployment, no hosted migration, no activation.

**The successor's first action:** report the inherited technical checkpoint in section 5 to the founder, then wait for the product-direction discussion before starting anything else.

## 1. Scope and decisions

### Scope
- **Lane brief:** the Business owner pilot, from [PR #900](https://github.com/lagarcess/argus/pull/900). The flow is capture, then review, then one expense, then find it again. That is stage **B1** of the [connected-flow spec](../specs/cuadrao-business-connected-flow-spec.md).
- **Isolation contract:** the [space slice plan, PR #910](https://github.com/lagarcess/argus/pull/910).
- **Roadmap:** stages B1, E0, B2 and L of the connected-flow spec. E0 is on hold; see [the E0 plan](../specs/cuadrao-business-e0-implementation-plan.md).

### Implemented and merged into integration (all default-off)

| PR | Merged as | What |
| --- | --- | --- |
| [#904](https://github.com/lagarcess/argus/pull/904) | `ee4acd50e` | Receipt review read model |
| [#901](https://github.com/lagarcess/argus/pull/901) | `d2d0c6d38` | Business web screens in the chat shell (`NEXT_PUBLIC_BUSINESS_PILOT_ENABLED`) |
| [#905](https://github.com/lagarcess/argus/pull/905) | `64833f6d2` | Private Storage for document sources, migration B1 `20261008100000`. **This is the Consumer Build 2 candidate.** |
| [#908](https://github.com/lagarcess/argus/pull/908) | `56f50b2f6` | Document preparation jobs, migration B2 `20261008110000` |
| [#909](https://github.com/lagarcess/argus/pull/909) | `fa5923529` | WhatsApp receipt intake, migration B3 `20261008130000` |
| [#913](https://github.com/lagarcess/argus/pull/913) | `7ec48872e` | Business API: review, confirm, completion by hand |
| [#914](https://github.com/lagarcess/argus/pull/914) | `6022747cb` | Personal and Business spaces (S1 to S3), migration B4 `20261008140000`, Business search, receipt next steps |
| [#918](https://github.com/lagarcess/argus/pull/918) | `20a88440c` | Chat separation (S4, the parts that change no model-facing text) |
| [#920](https://github.com/lagarcess/argus/pull/920) | `f5a2007cd` | Turning a switch off stops only new intake, without hiding saved data. Adds `ARGUS_BUSINESS_CHAT_ENABLED` (default off). |
| [#922](https://github.com/lagarcess/argus/pull/922) | `b30ef3bab` | Founder-approved copy for an AI result that couldn't be recovered |
| [#924](https://github.com/lagarcess/argus/pull/924) | `cd3231baa` | Test-only: shared in-memory sources, and sweepers that always stop |

Landing notes for #904, #901, #905, #908, #909, #913, #914, #918, #920 and #924 are in [the integration ledger](../specs/private-alpha-next-integration.md). The #924 entry is still unmerged on #925's branch.

### Founder approvals that stand
- **Copy:** approved and already in code.
  - The 10 WhatsApp replies (in `src/argus/domain/ingestion/whatsapp/replies.py`).
  - The two amount-field messages.
  - The Business search and receipt-state copy, with the founder's "AI result unknown" text.
  - The Business chat refusal: "Esta función no está disponible en el chat de tu negocio." / "This feature isn't available in your business chat."
  - The link label "Abrir mi chat personal" / "Open my personal chat", shown only where the function and destination are available.
- **Release cut:** Build 2 carries only #905 from the Business queue. #908, #909, #913 and #914 ship with the Business activation release.
- **Migration order,** approved as a plan only:
  - Consumer goes first: C0, then C1 (owned by Consumer on [#833](https://github.com/lagarcess/argus/issues/833)).
  - B1 ships with Build 2. B2, B3 and B4 ship with activation.
  - Each hosted step is a separate founder approval, which must include its read-only checks and synthetic smoke tests.
- **Rollback is a minimum compatible code version, not a code revert.** Once new-format data exists in hosted, any build that replaces or rolls back production must keep the Storage, deletion and space-isolation behavior. The response to a problem is to disable intake or Business access by flag, then fix forward. Schemas are never reverted. Evidence: [compatibility rehearsal](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-compat-rehearsal/evidence-log.md) and [flags-off rehearsal](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-flags-off/evidence-log.md).
- **AI test budget:** a per-call guard with a **hard $5.00 total** across both suites, all providers, judges, fallbacks and retries. Each call's maximum is reserved before it is sent, and if a call can't be covered the run stops and is marked incomplete.
- **Storage test interference is resolved, and accepted** (see section 3).

### What the successor must not infer or start
- **No product changes.** No E0, B2 or new features. No change to Business scope based on the accounting-firm interview.
- **No live AI eval calls.** The $5 cap is approved, but running a live eval is not.
- **No hosted actions.** No migration apply, flag change, deploy or hosted read. The October 8 hosted read was authorized once and is not standing permission.
- **No real WhatsApp messages.** Sending is not approved. The setup kit is [whatsapp-real-test-kit](../reports/evidence/cuadrao-business-owner-pilot/whatsapp-real-test-kit/README.md).
- **No merges without the founder,** including #925, #930, #900 and #910.
- **Don't turn Business chat on,** and don't mark #925's failing replay tests as xfail.
- **Docs-only PRs are normally not wanted.** This handoff PR is a founder-approved exception. Put landing notes inside code PRs.

## 2. Exact work state

**Integration** (`codex/private-alpha-next`) was `5d9a1f55aa03a56a1b8e3afb064f4b4c70e25aec` when this was written. It contains every merged PR above.

### Open PRs
| PR | Branch, head | State |
| --- | --- | --- |
| [#930](https://github.com/lagarcess/argus/pull/930) | `claude/fix-928-repair-audit` at `a1b5d9afa` | Fix for [#928](https://github.com/lagarcess/argus/issues/928). CI green and clean on this head. The Consumer lane's independent review found no blocking defects. **Ready for the founder to merge.** |
| [#925](https://github.com/lagarcess/argus/pull/925) | `claude/business-chat-tools` at `1426404d8` | Business chat tool restrictions (the model-facing part of S4), the per-call live-eval budget guard, and 14 Business eval cases. **Blocked on #930.** CI is red on the four `issue_600` replay tests, which is expected until #930 lands. `guest-release-gates (pinned)` also failed, at its *Install frontend dependencies* step, which is an infrastructure flake: rerun it. Do not merge until the Business scorecard is committed. |
| [#910](https://github.com/lagarcess/argus/pull/910) | `claude/business-space-slice-plan` at `c7fbd77a2` | Docs: the space slice plan, approved, plus the rollback section. Not merged. |
| [#900](https://github.com/lagarcess/argus/pull/900) | `codex/cuadrao-business-pilot-scope` at `d86a791d0` | Docs: the pilot scope, reconciled with #912. Not merged. |

### Merge order once the founder approves
1. #930.
2. Then reconcile #925 onto integration. CI must be green, and the four `issue_600` tests must pass unmodified.
3. #925 merges only after its Business scorecard is committed. That needs the live run, which is not authorized.

### Deployment candidates
These belong to Consumer, on [#833](https://github.com/lagarcess/argus/issues/833):
- Build 1 freeze: `cad1cbe1e`.
- Build 2 candidate: `64833f6d2`, which is Build 1 plus #905.

Business activation is not a candidate yet.

### Preserved branches (on GitHub, no PR)
- `claude/diagnostics-928-allowance` at `57e1fc100`: the #928 diagnostics, which replay the chat route under the turn allowance and count calls per measurement.
- `claude/evidence-storage-disconnect` at `b757fc9a0`: the durable Storage disconnect evidence.
- `claude/business-e2e-harness` at `512e8a9cc`: the local B1 end-to-end harness, `scripts/business_pilot_e2e/`, with its own README. Not product code.

### Local-only material
Optional; it is not needed to resume.
- The original machine has worktrees under `argus-worktrees/business-pilot-*`, all clean. Every commit in them is on GitHub, either merged or on a branch listed above.
- The local Supabase stacks `argus-biz-spaces` (ports 5778x), `argus-biz-pilot` (5718x) and `argus-biz-jobs` (5748x) are stopped, with their volumes kept. They are disposable; create your own.
- The session scratchpad held two large source copies used only for reproduction, plus logs. They are not needed.
- **Uncommitted work:** none.

## 3. Verification

| What | Covers commit | Result | Evidence |
| --- | --- | --- | --- |
| B1 end-to-end on local services: upload or WhatsApp, review, one expense, find after reload, isolation, flags off | #914 at `ce116998e`, then the merged attention and search head `380e38570` | Passed, after one copy defect was fixed in `e4f9f05f9` | [isolation-e2e](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-isolation-e2e/evidence-log.md), [b1-rerun](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-b1-rerun/evidence-log.md), [business-search](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-business-search/evidence-log.md) |
| S4 chat separation and the flag-off `/chat` byte identity | #918's branch | Passed | [s4-chat-surfaces](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-s4-chat-surfaces/) |
| Old code against new schema | Build 1 `5613364d0`, Build 2 `e43ea7fab` (local merge), activation `1d3e814b1` | Forward compatibility works; rolling code back after new-format data exists does not | [compat-rehearsal](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-compat-rehearsal/evidence-log.md) |
| Flags off with data present | `76273cf2c` | Passed. Separation holds and deletion works in every state | [flags-off](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-flags-off/evidence-log.md) |
| Storage disconnect test interference | integration `826ace6d4` | 20 of 20 alone, 20 of 20 combined. A foreign real-clock sweeper reproduces the failure in 3 of 5 runs | [storage-disconnect-proof](https://github.com/lagarcess/argus/tree/b757fc9a0e5d3b15584995b647e1613c380ed74e/docs/reports/evidence/cuadrao-business-owner-pilot/2026-10-08-storage-disconnect-proof), discussed on [#916](https://github.com/lagarcess/argus/pull/916) |
| #928 fix: the four `issue_600` replay tests | #925 `a3c33783d` alone, and merged with #930 `a1b5d9afa` (`3ef5d4f25`) | 4 fail alone, 4 pass merged | The recipe in [#930's comments](https://github.com/lagarcess/argus/pull/930) |
| Budget guard, offline | #925 `1426404d8` | 38 passed in the Linux container | `tests/evals/test_live_eval_budget.py`, `tests/evals/test_business_live_eval.py` |

**Storage: two separate statuses.** The founder accepted the durable evidence on October 8, so the reported **test-interference finding is resolved**. That covers the intermittent `document_version_conflict` in `test_disconnect_removes_the_object_and_keeps_confirmed_activity`. It **does not authorize hosted receipt access**, and it doesn't replace the **planned hosted deletion smoke test**: store one synthetic document, delete the synthetic account, and confirm the Storage object is gone. Both remain separate founder approvals, tracked by Consumer.

### How to reproduce
- **The Linux container.** Run in `argus-linuxci:base`, with no network:
  ```bash
  docker run --rm --network none -v <tree>:/work -w /work argus-linuxci:base bash -c "export POETRY_VIRTUALENVS_CREATE=false POETRY_NO_INTERACTION=1; poetry install --with dev,workflows --no-interaction >/dev/null 2>&1; python -m pytest <tests> -q --no-cov -p no:cacheprovider"
  ```
  That image was built locally by earlier lanes. Where it's missing, GitHub CI on a PR is the authoritative Linux run.
- **Postgres tests.** These need a disposable local Supabase stack, with `ARGUS_DISPOSABLE_DATABASE_URL`, plus `ARGUS_LOCAL_SUPABASE_URL`, `ARGUS_LOCAL_SUPABASE_ANON_KEY` and `ARGUS_LOCAL_SUPABASE_SERVICE_ROLE_KEY` for the Storage tests. Use one database per pytest process.
- **The live eval:** **not authorized; reference only.**
  ```bash
  ARGUS_RUN_LIVE_EVALS=1 ARGUS_LIVE_EVAL_BUDGET_USD=<approved> ARGUS_EVAL_FIXTURE_SET=all ARGUS_EVAL_ENV_FILE=<untracked file> ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider ARGUS_ASSET_PROVIDER_MODE=live_provider poetry run pytest tests/evals/test_measurement_eval_live.py -q
  ```
  The run refuses to start if the research rail, `PERPLEXITY_API_KEY`, or `ARGUS_DISCOVERY_SEARCH_PROVIDER=openrouter_web_search` is set. See `tests/evals/README.md`.

### Known failures and open findings
- **Mac-only.**
  - On macOS 27 the local venv's scipy fails to load, which breaks `tests/test_search_postgres.py::test_asset_rollup_pair_symbol_normalization_matches_memory_contract` and the Personal half of one #925 test. Use Linux.
  - `tests/test_home_country.py` fails locally on integration too, because of an environment confound.
- **Containers without git history.** Two prompt-freeze provenance tests fail there; they pass in a full checkout.
- **Baseline comparison.** The accepted 73-case Personal measurement ran *without* production's per-turn call allowance, and six of its cases needed more than seven calls. #925 measures under the allowance, so a new scorecard isn't like-for-like with that baseline for those cases. That is a stated, known consequence.
- **Budget guard: decisions still with the founder.**
  - DeepSeek once billed one token past its `max_tokens` (901 of 900, in 1,894 receipts). The guard reserves 2 × `max_tokens` for it, and a bill above its reservation stops the run.
  - The routing service may send a request to a costlier upstream than the pinned price assumes. That risk is bounded to one post, realistically under $0.30. The proposal was to set the guard's budget to $4.50 under the $5 cap.
- **Ceiling trade-off in #930.** After the seven ordinary permits are used, a last-resort focused repair gets one model instead of a fallback ladder. No recorded turn hits this.

## 4. Operational context
- **Local services:** Docker; the Supabase CLI for disposable stacks; Bun and Node for the web; Python 3.10 with Poetry.
- **Connector access** used by this lane: the `gh` CLI. Read-only Render and Supabase access was used once, on October 8, with explicit authorization.
- **Configuration names,** with defaults in [`.env.example`](../../.env.example):
  - Business: `ARGUS_BUSINESS_PILOT_ENABLED`, `ARGUS_BUSINESS_CHAT_ENABLED`, `NEXT_PUBLIC_BUSINESS_PILOT_ENABLED`.
  - Ingestion and documents: `ARGUS_INGESTION_ENABLED`, `ARGUS_DOCUMENT_EXTRACTION_ENABLED`.
  - WhatsApp: `ARGUS_WHATSAPP_*`, listed in [the WhatsApp activation packet](../specs/lanes/cuadrao-whatsapp-intake.md).
  - Document jobs: `ARGUS_DOCUMENT_JOBS_*`.
  - Credentials are supplied by an authorized operator in untracked env files: an OpenRouter key and Alpaca keys for the live eval, and Meta settings for WhatsApp. Never commit them.
- **Hosted facts.** These were verified once, **on October 8, 2026, with read-only access** (a Render API flag read and a read-only Postgres transaction). They have **not been re-verified since**.
  - No Business, ingestion or document flags are set on `argus-api` or `argus-app`.
  - Production ledger: 81 rows, head `20260914120000`.
  - No financial, document, Business or WhatsApp tables exist, and Storage has no buckets or objects.
  - Evidence: [live-readonly](../reports/evidence/cuadrao-business-owner-pilot/2026-10-08-live-readonly/evidence-log.md). Treat it as a historical observation, not current state.
- **Coordination.** Consumer owns the release candidate, the shared migration order and the hosted gates ([#833](https://github.com/lagarcess/argus/issues/833), [#916](https://github.com/lagarcess/argus/pull/916)). For #928, Business owns the fix and Consumer is the independent reviewer.

## 5. Next steps

**First: report this checkpoint to the founder, and wait for the product-direction discussion.** Start nothing else before it. The checkpoint is:
- what has merged;
- the open #930 and #925, and why #925 is blocked;
- the $5 cap with no live calls authorized;
- Business chat off;
- the two Storage statuses;
- the open decisions listed below.

**The successor can do these once the founder resumes the lane:**
1. Rerun the flaky `guest-release-gates (pinned)` job on #925.
2. After #930 is merged, reconcile #925 onto integration. Confirm green CI and that the four `issue_600` tests pass unmodified.
3. Keep #900 and #910 reconciled if the founder wants them merged.

**These need the founder's approval:**
- Merging #930, then #925, #900 and #910.
- The DeepSeek 2× reservation, and the $4.50 guard budget under the $5 cap.
- Running the live eval.
- Any hosted step: B1 to B4 applies, hosted receipt access, the hosted deletion smoke test, a real WhatsApp send.
- Any new product work, including E0, or a revised Business roadmap after the founder's reassessment.
