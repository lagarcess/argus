# Code reuse map for a financial-record import boundary

**Inspected commit.** `f0a90763b79e5625ac0a4789cdfa171cda023963`, equal to `origin/codex/private-alpha-next`. Every `path:line` reference resolves at that commit. References that start with `pilot:` resolve at `origin/codex/money-placement-pilot` instead, and only section 8 and one table row use them.

**Method.** Read-only `git show` and `git grep` against the commit. No tests ran and no provider was called. A bare `:N` reference points into the file named just before it in the same paragraph or bullet. "(inference)" marks a conclusion drawn from code that no test or document states.

**Question.** Which existing owners can a future connection or import boundary reuse, first for bank statements and later for bank-API data, and which contracts do not exist yet? The approved experience is MVEE sections 4, 5, and 12 (`docs/specs/argus-minimum-viable-ecosystem-experience.md:169-268` and `docs/specs/argus-minimum-viable-ecosystem-experience.md:386-431`). The undecided technical areas are listed in `docs/DOCUMENTATION_AUTHORITY.md:49-61`.

## Summary

- No production owner exists for financial accounts, transactions, balances, statements, households, or file upload. The 43 tables in `supabase/migrations/` hold rows such as profiles, conversations, messages, jobs, evidence, usage counters, memory, and shares. None holds a financial record.
- The reusable owners are generic mechanisms: the content-agnostic pending-artifact lifecycle, the compare-and-set message write, the applied-or-disclosed edit contract, the durable job table with its scope registry and `Idempotency-Key` contract, the typed fact-source vocabulary, the closed analytics registry, and the single browser-storage module.
- The shared research cache cannot receive private text on the current code path. Only discovery searches whose anchor symbols the provider catalog validated can enter it, and the cached provider query is machine text built from those symbols.
- The largest gaps are a record schema with minor-unit or `Decimal` money, a permission model beyond the guest or registered switch, a source-document store with retention, a sink-level log redaction rule, and a written reconciliation of the archived decision 8 storage rule with MVEE section 4.

## 1. Financial-record ingestion and correction

### Owners today

No production owner stores financial accounts, transactions, or balances.

- `docs/DATA_MODEL.md:55-79` lists the core entities, and none is a financial record. `docs/DATA_MODEL.md:7` says the MVEE's financial records "still need explicit schema and access-control design".
- The migrations create 43 tables, starting with `profiles` at `supabase/migrations/20260424000001_alpha_core.sql:14`. None stores an account, transaction, balance, statement, or holding. Regenerate the list with `git grep -n -i 'create table' f0a90763b -- supabase/migrations`.
- `docs/API_CONTRACT.md` has no account, transaction, or statement route. Backtest starting capital "is simulation capital only" (`docs/API_CONTRACT.md:2178-2179`).
- Every class named after an account in `src/argus` models a login, for example `AccountContext` (`src/argus/api/guest_access.py:57-67`) and `AccountCapabilities` (`src/argus/api/schemas.py:191`).
- The web app has no Accounts surface. The only "ledger" under `web/` is the decision ledger in the command palette (`web/components/sidebar/ChatCommandPalette.tsx:126`).
- No upload route exists. `python-multipart` is a dependency (`pyproject.toml:35`), but no route accepts `UploadFile`, and the storage bucket block is commented out (`supabase/config.toml:122`). `docs/reports/native-readiness-audit.md:119-120` reached the same result.

### Reusable

The chat proposal pattern exists, but only for simulations.

- `confirm_stage` reads `state.candidate_strategy_draft`, validates a launch payload and market-data coverage, and returns the outcome `await_approval` with a `confirmation_payload` (`src/argus/agent_runtime/stages/confirm.py:51-188`). Every field it builds is a strategy field, so a record draft needs its own stage (inference).
- The `pending_artifacts` module owns pending-card liveness "independent of its content" (`src/argus/domain/pending_artifacts.py:1-6`). It defines the `active`, `consumed`, `cancelled`, and `superseded` states (`:17-19`), consume-once (`:120-156`), restore (`:159-186`), and a guarded update that refuses a dead card (`:189-230`).
- The confirmation card (`src/argus/agent_runtime/stages/artifact_context.py:93-99`) and tool-result cards (`src/argus/api/routers/tool_results.py:92-99`) already use that owner. A record draft can be a third adapter (inference).
- One caution applies to consume-once. When the stamp write fails for an unexpected reason, it logs "proceeding unstamped" and returns `unstamped` (`src/argus/domain/pending_artifacts.py:149-155`). A backtest tolerates this because the durable `Idempotency-Key` reservation spends the confirmation identity, so a second Run replays the existing job (`docs/API_CONTRACT.md:259-264`). A record save needs an equivalent second guard (inference).
- The database owns the card write. `update_conversation_message_artifact` locks the owned conversation, then compares the card metadata and the latest message id before it writes (`supabase/migrations/20260810150000_serialize_message_artifact_update.sql:1-14`, `:20-47`).
- The edit contract module is generic. Its docstring says it never interprets input, never knows an artifact's fields, and never writes user-facing prose (`src/argus/domain/edit_contract.py:1-5`). `complete_edit_disclosure` returns a disclosure unless every requested edit was applied or refused (`src/argus/domain/edit_contract.py:13-44`). The rules in `docs/specs/private-alpha-next-conversational-edit-contract.md:85-108` also carry over: one operation list for chips and text, no silent drop, and a card that always shows backend state.
- The operation model does not carry over. `EditOperation` targets are strategy fields such as `asset`, `capital`, and `fees` (`src/argus/agent_runtime/artifact_edit_planner.py:36-65`). Card turns persist strategy facts only (`src/argus/domain/confirmation_turn_facts.py:15-34`).
- In-place card edits are off by default in code (`src/argus/domain/edit_contract_config.py:18-22`) and on for `argus-api` in `render.yaml:61-62`.

`tests/synthetic_ingestion/` is an isolated rehearsal of capture, proposal, review, confirmation, record, and correction on fictional files. It calls itself "not a product API or permission model" (`tests/synthetic_ingestion/harness.py:1`), and a test asserts that importing it loads no `argus` module (`tests/synthetic_ingestion/test_fixtures.py:152`). Its rules are a reference for a production contract, not code to import.

- A row has eight fields: `source_id`, `date`, `description`, `amount`, `currency`, `kind`, `account`, and `destination` (`tests/synthetic_ingestion/extract.py:12-21`).
- `field_issues` requires an ISO date, a positive dot-decimal amount with at most two places parsed as `Decimal`, the currency `DOP` or `USD`, the kind `expense`, `refund`, `income`, or `transfer`, and the destination `personal` or `household` (`tests/synthetic_ingestion/harness.py:15-43`).
- A row id is the SHA-256 of the file digest and row number, plus the stub digest when a stub exists. A re-import of the same bytes reuses the id (`tests/synthetic_ingestion/harness.py:114-124`).
- A row from another file is a `possible_overlap` when its `source_id`, account, and currency match, or when its date, description, amount, currency, kind, and account match (`tests/synthetic_ingestion/harness.py:46-50`, `:87-112`). A reviewer resolves overlaps. Nothing deletes them.
- A correction needs a reason and keeps the previous fields as a revision (`tests/synthetic_ingestion/harness.py:197-208`). Totals group by currency, then destination, then kind, and a refund reduces expenses (`:210-232`). Saving uses `os.replace` and restores the last committed state on failure (`:74-85`).

### Missing

- A record schema for accounts, transactions, balances, and import batches, with RLS.
- Draft and confirmed states for records, and a chat stage that proposes a record.
- A source-document store with retention.
- Production identity and duplicate matching for imported rows, transfer pairing, and balance reconciliation.
- Record revision history and undo.

`tests/synthetic_ingestion/README.md:88-94` lists the same open contracts. `docs/reports/synthetic-ingestion-evaluation.md:43-61` lists what a real Dominican statement must show before the harness rules apply to it.

### Unresolved contract

The archived decision 8 and MVEE section 4 conflict for a chat-typed expense, and no document reconciles them.

- Decision 8, founder-approved 2026-09-08, says a salary, expense, or debt the user types "lives in the conversation" and joins the memory never-store list. It adds "No new storage, no new retention surface" (`docs/archive/2026-09-17-argus-grounded-finance-roadmap.md:1791-1797`, framing at `:1697-1712`).
- MVEE section 4 says "The confirmed record is the durable financial fact" (`docs/specs/argus-minimum-viable-ecosystem-experience.md:177`). The decision log approves that ingestion experience on 2026-09-26 without naming decision 8 (`docs/specs/argus-decision-log.md:17`), and `docs/DOCUMENTATION_AUTHORITY.md:54` keeps the record schema undecided.
- `docs/reports/payment-ledger-reuse-assessment.md:67` still calls decision 8 "the storage rule" and cites `docs/specs/argus-grounded-finance-roadmap.md`, which is now a redirect (`docs/specs/argus-grounded-finance-roadmap.md:1-10`).
- Three documents use the label "decision 8" for a different rule, that country and currency are stated and never inferred (`src/argus/domain/home_country.py:9`, `docs/DATA_MODEL.md:191-193`, `docs/API_CONTRACT.md:1048`).
- Code enforces decision 8 only in memory, and only in part. `NEVER_STORABLE_FLAGS` holds `broker_credential` and `raw_conversation` (`src/argus/api/personalization_memory_assessor.py:23-29`). Other sensitive text is suppressed because any flag forces `restricted` (`src/argus/api/personalization_memory_assessor.py:54-77`) and policy suppresses restricted content (`src/argus/memory/policy.py:185-189`). One LLM call assigns the flags. Its definitions name salary figures and account balances but not expenses or debts (`src/argus/llm/memory_sensitivity.py:41-55`), so a plain expense statement can classify as clear (inference).

The founder still has to say which rule governs a chat-typed expense after the user confirms it. A separate technical choice is whether confirmed drafts live in message metadata or in their own table.

## 2. Authentication and permissions

### Owners today

- `current_user` is the one identity dependency (`src/argus/api/dependencies.py:393-533`). It reads a bearer token or an `sb-*auth-token` cookie (`:419-446`) and asks Supabase Auth to validate it through `client.auth.get_user` (`src/argus/api/dependencies.py:457-466`, `src/argus/domain/supabase_guest_accounts.py:31-35`). The API does not verify the JWT signature itself.
- A second check decodes the token without verifying it and reads only `session_id` and `sub` (`src/argus/api/auth_sessions.py:66-80`). It then requires a live `auth.sessions` row (`:27-48`). The check fails closed with 503 when the database is unreachable (`:51-63`, `src/argus/api/dependencies.py:475-482`), so a revoked session stops working at once.
- Mock auth turns on when `NEXT_PUBLIC_MOCK_AUTH` or `ARGUS_MOCK_AUTH` is `true` (`src/argus/api/dependencies.py:394-408`). Only configuration keeps it off in production (`render.yaml:33-34`, `render.yaml:180-181`). The environment check `_production_like_environment` feeds only the cookie `Secure` flag (`src/argus/api/dependencies.py:371-386`).
- A guest is an anonymous Supabase user. An `is_anonymous` token needs an active guest workspace or gets 403 `guest_session_expired` (`src/argus/api/dependencies.py:492-525`). A database constraint fixes a workspace's life at 7 days (`supabase/migrations/20260724101324_add_guest_workspaces.sql:64-77`).
- A registered user passes the private-alpha or public-access gate (`src/argus/api/dependencies.py:527-529`, `src/argus/api/guest_access.py:48-54`).
- Permissions are a closed capability set with a 403 `account_conversion_required` denial (`src/argus/api/dependencies.py:289-324`). Guests get `False` for a second conversation, conversation management, decision saving, and account management (`src/argus/api/guest_access.py:91-103`). `docs/reports/native-readiness-audit.md:320-321` calls `AccountCapabilities` "a guest/registered switch, not a resource permission model".
- The backend reads and writes with the service-role key (`src/argus/domain/supabase_gateway.py:163-187`), which bypasses RLS. Ownership is an explicit filter in application code, with 68 `.eq("user_id"` calls under `src/argus/domain`, and a `p_user_id` check inside SQL functions (`supabase/migrations/20260810150000_serialize_message_artifact_update.sql:42-47`).
- RLS is a second check. The primary rule is `user_id = auth.uid()` (`docs/DATA_MODEL.md:2291-2299`). Guest rows add restrictive policies on the `is_anonymous` claim and an active workspace (`docs/DATA_MODEL.md:2323-2334`, `supabase/migrations/20260724101324_add_guest_workspaces.sql:260`, `:282`). Server-only tables such as `cost_ledger_entries`, the nine memory tables, `public_excerpt_snapshots`, and the checkpoint tables enable RLS with no client policy (inference from parsing every `create policy` in `supabase/migrations/`).
- The web client uses Supabase for auth calls only (`web/lib/supabase-client.ts:25`) and reads data through the Argus API. Profile writes go through one serialized path (`web/lib/profile-writes.ts:10-28`) to `PATCH /me` (`docs/API_CONTRACT.md:3067`).
- A profile row belongs to its `auth.users` row and cascades on delete (`supabase/migrations/20260424000001_alpha_core.sql:14-15`). Registered-only fields such as `country` use restrictive policies (`supabase/migrations/20260911120000_add_profile_home_country.sql:35`, `:46`).

### Reusable

Session validation and revocation, the account context, the capability denial, service-role writes with owner filters, and the owner-plus-restrictive RLS pattern fit a single owner's records as they are (inference).

### Missing

- Resource-level permissions that separate owning, viewing, and editing a record.
- Grants that give a second person access to one record.
- A step-up or re-authentication check before a bank connection.
- A code-level refusal of mock auth in production.

### Unresolved contract

Whether guests may import at all, because guest persistence is still open (`docs/specs/argus-minimum-viable-ecosystem-experience.md:316`). Also which capability gates import, and how per-record permissions reach both the API filters and RLS.

## 3. Household and private-account boundaries

### Owners today

- No household, membership, invitation, or joint-account model exists in `src/`, `supabase/`, or `web/`. The only "membership" is a temporary SQLite table inside decision search (`src/argus/api/memory_ledger_index.py:135`). `docs/DATA_MODEL.md:7`, `docs/ARCHITECTURE.md:7`, `AGENTS.md:127-130`, and `docs/reports/native-readiness-audit.md:315-321` all record the gap.
- Conversation sharing is the only path that shows one person's content to another. It freezes a sanitized snapshot into `public_excerpt_snapshots`, and the public read "never queries the source conversation, message, run or provider" (`docs/DATA_MODEL.md:1450-1466`). The table has RLS with no policy and no grant, so only the backend reads it (`docs/DATA_MODEL.md:1692-1700`). Revocation is one way, and deleting the source revokes the receipt (`docs/DATA_MODEL.md:1643-1675`).
- Sharing is off in production (`render.yaml:59-60`, `render.yaml:194-195`), and `src/argus/api/public_excerpts.py:74` reads the flag. Guests cannot create receipts (`docs/specs/conversation-sharing.md:144`).
- The sharing policy is "Shareable by default; refuse only what is private" (`docs/specs/conversation-sharing.md:10`). It dropped the refusals for credential-shaped text and for answers that used memory (`:51-56`). Each new leaf freezes the question and the final answer text (`:84-89`), and a receiver's copy survives revocation (`:131-133`).
- A shared calculation publishes the inputs the user stated. `_selected_input` keeps an input when its visibility is `public` or its source kind is `page` or `user` (`src/argus/domain/public_excerpt_turns.py:369-373`), although `ToolInputFact.visibility` defaults to `private` (`src/argus/domain/tool_contracts.py:133`).
- Tests cover cross-owner isolation, for example `tests/test_public_excerpt_receipts.py:598` and `tests/test_tool_result_recompute.py:243`. The dev-store helper `memory_object_visible` treats an unknown owner as visible (`src/argus/api/memory_ownership.py:6-13`), so it is not a model for record access.

### Reusable

A frozen snapshot, revocation when the source goes away, and backend-only reads are a working pattern for showing a view of data without granting access to the data (inference). The single-owner RLS pattern from section 2 is the starting point for anything shared.

### Missing

Households, memberships, invitations and acceptance, the separation of ownership from visibility and edit rights, joint-account identity across two importers, contribution records, the effects of leaving a household, and aggregation that excludes unshared facts (`docs/specs/argus-minimum-viable-ecosystem-experience.md:396-425`).

### Unresolved contract

The membership lifecycle, its RLS, revocation, and retention (`docs/DOCUMENTATION_AUTHORITY.md:55`). A second question follows from the sharing policy. If the owner selects a turn that quotes a private record, the current rules freeze that text into a public page, so sharing needs an explicit rule for record-derived turns (inference).

## 4. Evidence, source provenance, and the research cache

### Owners today

- `evidence_artifacts` holds an immutable proof package per completed backtest (`supabase/migrations/20260619000001_p1_evidence_decision_spine.sql:36-51`). Its `artifact_type` check admits only `backtest` (`:43`), and `UNIQUE(user_id, source_run_id)` makes capture idempotent (`:50`). A trigger freezes identity, digest, and payload (`supabase/migrations/20260621053126_enforce_p1_evidence_immutability.sql:33`). `docs/DATA_MODEL.md:1082-1085` admits other context only after "its artifact type, source, timestamp, and ownership contract are explicitly specified".
- Provenance is typed at a few boundaries and a dict convention elsewhere.
  - `ToolFactSourceKind` is `user`, `page`, `market_data`, `assumption`, `computed`, or `not_found` (`src/argus/domain/tool_contracts.py:31-36`). Only a page carries a title and URL, and only a page or market data carries a date (`src/argus/domain/tool_contracts.py:91-108`).
  - `AnswerCalculationInput` names its source (`page`, `market_data`, `user`, or `assumption`), `source_url`, `as_of`, and ISO `currency` (`src/argus/domain/calculations/answer_request.py:72-111`).
  - `RetrievedRow` carries `as_of` and `source_url` for each research figure (`src/argus/domain/research/contracts.py:82-85`).
  - `ResolutionProvenance` records how a symbol was validated (`src/argus/agent_runtime/state/models.py:204-213`), and `MemoryProvenance` points at a canonical source row (`src/argus/memory/contracts.py:94-101`).
  - Strategy drafts carry a `"field_provenance"` dict in 27 files under `src/`. Regenerate the count with `git grep -l '"field_provenance"' f0a90763b -- src`.
- The shared research cache is an in-process dict of at most 512 entries (`src/argus/domain/research/cache.py:89`, `:154-157`). It accepts only `SearchResultPacket` values (`:221-227`), keyed by a hash of the contract version, provider query, provider id, and result limit (`:160-173`). Only the `perplexity_direct` provider gets a key (`:179-188`), and entries live 300 seconds (`:193-200`).
- The runtime decides eligibility before it builds the cache object. `_public_anchor_search` returns `False` for a category request, a free-text description, or a request without anchors, and it requires every anchor to resolve through the provider catalog with the expected asset class (`src/argus/agent_runtime/research_find.py:32-64`, gate at `:91-95`). The provider query is machine text built from those symbols, "never user prose" (`src/argus/agent_runtime/discovery/composer.py:532-553`). Grounded research answers never enter the shared cache (`src/argus/agent_runtime/research_grounded.py:773-776`, `:2058-2060`).
- Tests cover the isolation. `tests/research/test_research_cache_isolation.py:83-84` puts "Private account ... balance ..." text into the message, the screening criteria, and the sector, and asserts that nothing reaches shared storage. Other cases cover free-form questions (`:34`), an unvalidated anchor (`:409`), and a free-form packet under a valid key (`:453`). Validated searches are shared across users on purpose (`tests/research/test_research_cache.py:44`).
- The profile country goes to the research provider as the reader's location (`docs/DATA_MODEL.md:191-193`, `src/argus/agent_runtime/state/models.py:363-365`).

### Reusable

The cache predicate and its tests fit as they are. On the current code path, banking text cannot reach the cache key or the cached packet, because both come from catalog-validated symbols (inference, partly proven by the private-context test). `ToolFactSource` and `evidence_artifacts` are the nearest precedents for record provenance and for an immutable source document, and both need new kinds.

### Missing

- Source kinds for extracted and connected data. MVEE section 5 separates user-entered, extracted, connected, and calculated information (`docs/specs/argus-minimum-viable-ecosystem-experience.md:258`).
- Separate activity, statement, and capture or refresh dates (`docs/specs/argus-minimum-viable-ecosystem-experience.md:259`).
- A source-document artifact type with an owner and a retention period.
- A written rule that any store holding record-derived content is per-owner and never shared.

### Unresolved contract

The provenance and date fields of a record, where source documents live and for how long, and whether imported statement text may ever reach a research provider.

## 5. Jobs, retries, idempotency, and observability

### Owners today

- `backtest_jobs` is already the durable job table for four scopes: `chat.run_backtest`, `backtests.run`, `chat.research`, and `workflows.proof` (`src/argus/domain/backtest_job_scopes.py:21-35`). That module owns every scope value and renders the SQL check constraint, and a test fails on a scope spelled anywhere else (`src/argus/domain/backtest_job_scopes.py:1-15`, `:40-52`).
- `Idempotency-Key` has a full contract (`docs/API_CONTRACT.md:193-264`). A key is 1 to 128 visible ASCII characters, reserved per `(user_id, operation_scope, key)`, replayed before any quota check, and refused with 409 `idempotency_conflict` when reused for a different canonical identity.
- Two routes read the header (`src/argus/api/routers/backtest.py:66`, `src/argus/api/routers/agent.py:265-269`). Validation and canonical hashing live in `src/argus/domain/backtest_admission.py:98-131`. A unique index holds the reservation (`supabase/migrations/20260722000002_atomic_backtest_admission.sql:16-20`), and one database function admits a job in one transaction (`:1-4`, `:25-30`).
- `chat_turn_lifecycles` gives each ordinary chat turn one lifecycle row that only a compare-and-set function changes, keyed by the user message and correlated by `request_id` (`docs/DATA_MODEL.md:671-730`).
- Each request takes its id from `x-request-id` or gets a new one, and the response echoes `X-Request-Id` (`src/argus/api/dependencies.py:222-250`). `cost_ledger_entries` stores `request_id` and a required `correlation_id` (`supabase/migrations/20260702000001_add_cost_ledger_entries.sql:30-31`).
- Research provider calls try at most 3 times with doubling backoff (`src/argus/domain/research/perplexity_agent.py:445-448`). A failure is asked again automatically only when the provider cannot have started paid work (`src/argus/domain/research/contracts.py:201-222`).
- Loguru runs with `diagnose=False` and `backtrace=False`, and `exception_origin` reports only a file name and line (`src/argus/log_sink.py:10-26`). Commit `2ea968156` removed private content from known log calls. `tests/agent_runtime/test_private_log_content.py` attaches a real sink and checks 13 cases across OpenRouter, validation, routing, calculation, market data, and research calls (first case at `tests/agent_runtime/test_private_log_content.py:56`). `docs/reports/evidence/687/README.md:8-22` lists the covered calls, and `:35-36` records that all 13 cases failed before the fix and pass after it. No sink filter scrubs content, so a new log call has no protection until someone adds a case for it (inference).
- Commit `627d21e6b` made analytics a closed registry. Each event is a strict Pydantic model of literals, booleans, and bounded integers, so "an amount, a name, an email, or any other free text cannot be represented" (`src/argus/observability/analytics_events.py:1-12`, `:116-138`). The sink sends nothing unless `registered_payload` validates the event again (`src/argus/observability/envelope.py:247-250`, `src/argus/observability/analytics_events.py:351-389`). The web app has no analytics library, and the runbook forbids frontend PostHog, autocapture, and session replay (`docs/PRIVATE_LAUNCH_RUNBOOK.md:780-781`).
- `docs/DATA_MODEL.md:1447-1448` says cost rows never store prompts, transcripts, credentials, balances, or holdings. The writer copies provider token usage and has no content check (`src/argus/observability/cost_ledger.py:49-51`), so the rule holds by construction (inference).
- The runtime keeps the last 6 thread messages per turn (`src/argus/agent_runtime/runtime.py:39`), and the interpret stage passes them to the interpreter model (`src/argus/agent_runtime/stages/interpret.py:421`). Each turn also carries a `UserState` with language, country, and currency (`src/argus/agent_runtime/state/models.py:359-370`). Memory recalls are added after a turn and never feed back into a request (`docs/API_CONTRACT.md:6351-6354`).
- A feedback submission emails the user's full message to the support inbox through Resend (`src/argus/api/feedback_notification.py:40-52`, `:86-91`).

### Reusable

- An import or refresh job can be a new scope in `backtest_jobs`, with the same `Idempotency-Key` contract, canonical hashing, and database admission. The table carries backtest columns, so this is an adaptation, not a drop-in.
- The analytics registry already refuses amounts and free text.
- `request_id` and `correlation_id` can join import events to cost rows as they are.
- The research provider's rule of asking again only when no paid work started is a model for bank refresh retries (inference).

### Missing

- A redaction filter at the log sink, or a test that scans every log call for record fields.
- An import scope and a refresh scope.
- A bank-connection state model with connection state, last successful refresh, and re-authentication status (`docs/specs/argus-minimum-viable-ecosystem-experience.md:252`).
- A rule that keeps record contents out of model prompts by default. Today any figure a user types enters the 6-message window.

### Unresolved contract

Job and event contracts for the new surfaces (`docs/DOCUMENTATION_AUTHORITY.md:56`), a redaction rule for record fields in logs and error paths, and which record facts a model prompt may include.

## 6. Money and currency

### Owners today

- Calculations compute in `float`, and backtest result money reaches the display code as `float` (`src/argus/domain/result_money.py:60-63`). `Money` holds a float amount and an ISO-shaped code, and it refuses to add two currencies (`src/argus/domain/finance/money.py:12-43`). No file under `src/argus/domain/calculations/` or `src/argus/domain/finance/` uses `Decimal`. Confirmation edits take `float` capital (`src/argus/api/confirmation_schemas.py:79-89`).
- `Decimal` appears at the display and billing edges. `rounded_result_money` converts a float with `Decimal(str(value))` and rounds half up (`src/argus/domain/result_money.py:60-63`). The cost ledger stores `numeric(18, 8)` amounts with a default currency of `USD` (`supabase/migrations/20260702000001_add_cost_ledger_entries.sql:52-53`).
- `currency_fraction_digits` is the display precision of a backtest result, not a per-currency table. A run shows cents only when its peak stays under 1,000 and shows 0 decimals otherwise (`src/argus/domain/result_money.py:21-39`, `web/argus_display_contract/result_display_policy.json:2-4`). `format_result_money` always writes `$` (`src/argus/domain/result_money.py:66-69`). The web reads the same policy file (`web/lib/result-money.ts:9-25`).
- The ISO 4217 list comes from Babel's CLDR data (`src/argus/domain/research/contracts.py:22-25`). Calculation inputs accept only tender currencies in use (`src/argus/domain/calculations/_shared.py:53-60`).
- `_calculation_currency` owns stated currency. It prefers the denomination of a stated amount, then an explicit currency input, then the profile currency, and finally `USD` with a disclosure note (`src/argus/agent_runtime/answer_calculation.py:762-823`, default at `:58`, note code at `:73`).
- DOP support comes from data. A profile's currency is the first CLDR tender currency of its declared country unless the user overrides it (`src/argus/domain/home_country.py:1-11`, `docs/DATA_MODEL.md:153-154`). Nothing in `src/` parses `RD$`, and no FX conversion exists.

### Reusable

The CLDR currency list, the country-to-currency owner, the half-up rounding mode, and the refusal to add two currencies fit records as they are (inference). The float `Money` type and the `$` formatter do not.

### Missing

An amount type in integer minor units or `Decimal`, per-currency fraction digits, parsing for `RD$`, `US$`, and `1.234,56`, and an FX policy. `docs/reports/payment-ledger-reuse-assessment.md:9-21` recommends integer minor units, `Decimal` conversion with a named rounding mode, and balancing each currency alone.

### Unresolved contract

The money arithmetic contract for records (`docs/DOCUMENTATION_AUTHORITY.md:54`), and the rule for an unqualified amount. The calculation path defaults to `USD` with a note, while MVEE section 5 says "Do not infer dollars or pesos from an unqualified amount" (`docs/specs/argus-minimum-viable-ecosystem-experience.md:260`).

## 7. Updates and data controls

### Owners today

- No updates inbox, notification preference, push channel, or reminder job exists. `docs/PRODUCT.md:99` marks notifications "Hidden/flagged for Alpha". `conversation_read_states` stores one read boundary per conversation and "is not an event log" (`docs/DATA_MODEL.md:758-772`). The analytics registry defines `reminders_opted_in` and `reminders_opted_out` with an `email` or `push` channel (`src/argus/observability/analytics_events.py:177-186`), and no code emits them.
- The system sends two emails. `send_access_welcome_email` welcomes an approved person (`src/argus/domain/access_approval_email.py:140-156`), and feedback goes to the support inbox (`src/argus/api/feedback_notification.py:13`). Neither concerns a user's finances.
- Conversations are soft-deleted, one at a time or all at once (`src/argus/api/routers/conversations.py:382`, `:480`, `docs/API_CONTRACT.md:3240-3244`).
- Memory records support delete, reset, and export behind a flag and an `admin` or `developer` role (`src/argus/api/routers/personalization_memory.py:261`, `:360`, `src/argus/api/personalization_memory.py:33`, `docs/API_CONTRACT.md:6306-6348`). No other data has an export.
- Account deletion is a feedback message of type `account_deletion_request` (`src/argus/api/schemas.py:954`, `src/argus/api/routers/feedback.py:28`). After an operator deletes the auth user, `on delete cascade` removes the profile and the user's rows (`supabase/migrations/20260424000001_alpha_core.sql:15`, `:30`, `:45`). Cost rows stay with `user_id` set to null (`supabase/migrations/20260702000001_add_cost_ledger_entries.sql:24`).
- Guest retention runs only when an operator runs it. `scripts/ops/scheduled_maintenance.py:36-60` runs guest retention first. `render.yaml` defines two web services and no cron job (`render.yaml:2-3`, `render.yaml:158-159`), and `.env.example:268-271` and `docs/PRIVATE_LAUNCH_RUNBOOK.md:786-799` say to run the script by hand. `docs/DATA_MODEL.md:426` says it runs daily, which contradicts the runbook.

### Reusable

The memory export document, delete with provider reconciliation, and reset are the only data-control precedents. The profile cascade would remove any future record keyed to `profiles.id` when an operator deletes the account (inference).

### Missing

Self-service account deletion, a general export, hard deletion of a record, retention and purge for source files, a scheduled retention job, an updates inbox, notification preferences, and delivery channels.

### Unresolved contract

Retention and deletion for records and source documents (`docs/DOCUMENTATION_AUTHORITY.md:55`, `docs/specs/argus-minimum-viable-ecosystem-experience.md:267`, `docs/specs/argus-minimum-viable-ecosystem-experience.md:320`), notification delivery and scheduling (`docs/DOCUMENTATION_AUTHORITY.md:58`), and who runs retention on a schedule.

## 8. The money placement pilot branch, outside the inspected base

`origin/codex/money-placement-pilot` is not on the integration branch. Its tip is `026be6d32` (2026-09-22), the merge of PR #664. PR #658, the Clara platform, merged into it at `5430d98d6`. The tip is not an ancestor of `f0a90763b`.

- It adds a separate top-level `money-view/` tree and a `money-view` CI workflow, edits `.github/workflows/ci.yml`, and changes nothing under `src/argus/` or `supabase/`.
- `AccountCreate` takes a kind, an ISO currency, and a `Decimal` opening balance (`pilot:money-view/server/platform/ledger_contracts.py:27-32`).
- `TransactionCreate` takes a signed `Decimal` amount, a `posted` or `pending` status, and a required `idempotency_key` (`pilot:money-view/server/platform/ledger_contracts.py:45-68`). Connect, sync, and statement-mapping commands follow (`pilot:money-view/server/platform/ledger_contracts.py:78-95`).
- SQLite tables `p_accounts`, `p_transactions`, `p_transaction_splits`, `p_imports`, and `p_import_rows` live in `pilot:money-view/server/platform/ledger.py:62-86`, and `p_households` and `p_memberships` in `pilot:money-view/server/platform/identity.py:62-66`.
- The store is "SQLite persistence for Clara's local, single-owner workspace" (`pilot:money-view/server/store.py:1`), so none of it uses Supabase or RLS.

## Reuse table

| Concern | Existing owner (file:line) | Reuse as-is / adapt / absent | Unresolved contract |
| --- | --- | --- | --- |
| Account, transaction, and balance records | None. Core entities at `docs/DATA_MODEL.md:55-79` | Absent | Record schema, RLS, and migrations (`docs/DOCUMENTATION_AUTHORITY.md:54`) |
| File upload and source documents | None. Bucket commented out at `supabase/config.toml:122` | Absent | Formats, limits, storage, and retention (`docs/specs/argus-minimum-viable-ecosystem-experience.md:320`) |
| Chat proposal of a record | `src/argus/agent_runtime/stages/confirm.py:51-188`, strategy only | Adapt, as a new stage | Record draft shape and batch confirmation |
| Draft liveness and consume-once | `src/argus/domain/pending_artifacts.py:17-230` | As-is as a new adapter, plus a second duplicate guard | Whether drafts live in message metadata or a table |
| Card compare-and-set write | `supabase/migrations/20260810150000_serialize_message_artifact_update.sql:20-47` | As-is | Whether drafts live in message metadata or a table |
| Applied-or-disclosed edits | `src/argus/domain/edit_contract.py:13-44` | As-is | Record edit targets |
| Edit operation model | `src/argus/agent_runtime/artifact_edit_planner.py:36-65` | Adapt, new targets | Undo and revision history |
| Import identity, overlap, and correction | `tests/synthetic_ingestion/harness.py:15-232`, test-only | Adapt, as reference rules | Cross-file identity, transfer pairing, and reconciliation |
| Storage rule for typed figures | `docs/archive/2026-09-17-argus-grounded-finance-roadmap.md:1791-1797` | A rule, not code | Reconcile with `docs/specs/argus-minimum-viable-ecosystem-experience.md:177` |
| Memory never-store for money facts | `src/argus/api/personalization_memory_assessor.py:23-29`, `src/argus/llm/memory_sensitivity.py:41-55` | Adapt, name expenses and debts | Whether records may ever inform memory |
| Session validation and revocation | `src/argus/api/dependencies.py:393-533`, `src/argus/api/auth_sessions.py:27-80` | As-is | Step-up check before a bank connection |
| Mock auth in production | `src/argus/api/dependencies.py:394-408`, `render.yaml:33-34` | Adapt, add a code guard | None named |
| Guest identity and lifetime | `src/argus/api/dependencies.py:492-525`, `supabase/migrations/20260724101324_add_guest_workspaces.sql:64-77` | As-is | Whether guests may import (`docs/specs/argus-minimum-viable-ecosystem-experience.md:316`) |
| Capability gate | `src/argus/api/dependencies.py:289-324`, `src/argus/api/guest_access.py:91-116` | Adapt, add an import capability | A resource permission model |
| Owner filters under the service role | `src/argus/domain/supabase_gateway.py:163-187` | As-is | Filters for shared records |
| Single-owner RLS | `docs/DATA_MODEL.md:2291-2334` | As-is | Household RLS (`docs/DOCUMENTATION_AUTHORITY.md:55`) |
| Households, members, and joint accounts | None | Absent | Membership lifecycle and permissions (`docs/specs/argus-minimum-viable-ecosystem-experience.md:396-425`) |
| Sharing snapshots | `docs/DATA_MODEL.md:1450-1700`, `src/argus/domain/public_excerpt_turns.py:369-373` | Adapt. Shares publish stated inputs and question text today | Refusal rule for record-derived turns |
| Fact provenance | `src/argus/domain/tool_contracts.py:31-108` | Adapt, add extracted and connected kinds | Record provenance and dates (`docs/specs/argus-minimum-viable-ecosystem-experience.md:258-259`) |
| Immutable source evidence | `supabase/migrations/20260619000001_p1_evidence_decision_spine.sql:36-51` | Adapt. `artifact_type` admits `backtest` only | Source-document type, owner, and retention |
| Shared research cache eligibility | `src/argus/agent_runtime/research_find.py:32-64`, `src/argus/domain/research/cache.py:160-227` | As-is | Written per-owner rule for record stores |
| Durable jobs and scopes | `src/argus/domain/backtest_job_scopes.py:21-52` | Adapt, new scopes | Import and refresh job contract |
| `Idempotency-Key` | `docs/API_CONTRACT.md:193-264`, `src/argus/domain/backtest_admission.py:98-131` | As-is | Canonical identity of an import |
| Provider retry | `src/argus/domain/research/contracts.py:201-222`, `src/argus/domain/research/perplexity_agent.py:445-448` | Adapt | Refresh failure and re-authentication states |
| Request and correlation ids | `src/argus/api/dependencies.py:222-250`, `supabase/migrations/20260702000001_add_cost_ledger_entries.sql:30-31` | As-is | None |
| Log privacy | `src/argus/log_sink.py:10-26`, `tests/agent_runtime/test_private_log_content.py:56` | Adapt. Per-call tests only | Sink-level redaction of record fields |
| Product analytics | `src/argus/observability/analytics_events.py:1-12`, `src/argus/observability/analytics_events.py:351-389` | As-is | Which import events exist |
| Model prompt context | `src/argus/agent_runtime/runtime.py:39`, `src/argus/agent_runtime/state/models.py:359-370` | Adapt | Which record facts a prompt may see |
| Record money type | `src/argus/domain/finance/money.py:12-43`, float | Absent for records | Minor units or `Decimal` (`docs/DOCUMENTATION_AUTHORITY.md:54`) |
| Currency list and country currency | `src/argus/domain/research/contracts.py:22-25`, `src/argus/domain/home_country.py:1-11` | As-is | Per-currency fraction digits |
| Stated currency | `src/argus/agent_runtime/answer_calculation.py:762-823` | Adapt. It defaults to `USD` | Unqualified amounts (`docs/specs/argus-minimum-viable-ecosystem-experience.md:260`) |
| Money display | `src/argus/domain/result_money.py:21-69` | Adapt. It writes `$` only | Display per currency |
| Updates inbox and notifications | None. Status at `docs/PRODUCT.md:99` | Absent | Channels, preferences, and scheduling (`docs/DOCUMENTATION_AUTHORITY.md:58`) |
| Data export | `src/argus/api/routers/personalization_memory.py:261`, memory only | Adapt | Record export format |
| Account and record deletion | `src/argus/api/schemas.py:954`, `supabase/migrations/20260424000001_alpha_core.sql:15` | Adapt | Self-service deletion and source purge |
| Retention job | `scripts/ops/scheduled_maintenance.py:36-60`, run by hand | Adapt, needs a scheduler | Who runs retention and when |
| Browser storage | `web/lib/browser-storage.ts:1-46` | As-is | Whether any record data may be cached on a device |
| Pilot ledger, not on the integration branch | `pilot:money-view/server/platform/ledger_contracts.py:27-68` | Absent on the base branch | Whether any pilot contract is promoted |
