# Frozen local chat backend review

Reviewed 2026-09-21. **Not clean: two P2 integration findings.** No application edits.

The seven files in `review-packages/chat/manifest.json` matched their frozen SHA-256 entries. Working copies also matched when checked before verification. The reviewed `chat.py` hash is `1a2995bb38926ca9260e9bdca1a198da3142dfa82c49ff93ca810534fe67d38c`.

Scope: chat kernel, typed plans/cards, graph, model boundary, supplied chat tests, `chat-report.md`, and `money-view/docs/experience/ARCHITECTURE.md`. Existing owner interfaces were inspected only where the chat integration uses them; this does not duplicate the separate commands facade/core review.

## Findings

### P2 — Resolve explicit request currency consistently before dispatch

Location: frozen `money-view/server/platform/chat.py:725-736`, with the same boundary issue in `chat.py:665-673` and precedence at `chat.py:550-551`.

The read handler builds `Parameters` only from the plan. Without a selected account, `TurnRequest.currency` is never applied. A prepared `net_worth` read with top-level `currency="DOP"` and empty parameters therefore completes with USD facts from the parameters' default. This is a reachable prepared-action/API path; it does not depend on model quality. A semantic plan that omits currency has the same outcome even though the request carries explicit currency.

The calculation path shows the complementary conflict problem: selecting an owned DOP account while explicitly submitting `currency="USD"`, with no currency in calculation arguments, completes in DOP instead of returning a conflict. It checks plan argument currency against the account but never checks the request currency. Accountless calculation and record paths likewise allow a plan currency to win over an explicitly different request currency.

Observed probe output:

```json
{"status":"completed","code":"calculated","explicit":"USD","account":"DOP","card_currency":"DOP"}
{"status":"completed","code":"grounded_records","fact_currencies":["USD","USD","USD"]}
```

The second probe explicitly requested DOP. The underlying calculations/facts are canonical, but the chat applies a different monetary context from the user's explicit selection. This contradicts the reviewed contract that explicit currency is preserved and conflicts fail explicitly.

Suggested fix: resolve request, plan and owned-account currency through one chat boundary and pass the validated effective currency to each capability. Preserve an artifact's prior currency when no change was stated; reject conflicting explicit inputs instead of silently selecting one. Verify prepared and semantic reads/calculations/records, accountless and account-bound cases, and continuation with omitted currency.

### P2 — Align household-visible conversations with creator-owned proposal projection

Location: frozen `money-view/server/platform/chat.py:225-230`, reached through household-scoped `_conversation` and `list_conversations` at `chat.py:101-110` and `chat.py:161-184`.

Conversations are listed and authorized by household, but transcript hydration calls `CommandService.get(context, proposal_id)` for every proposal card. That command interface intentionally requires the proposal's creator user. After one household member creates a proposal, a second member can see the conversation in the list but cannot open it: hydration fails with `404 proposal_not_found`. The same failure enters `planning_packet` through transcript loading and prevents a natural-language continuation in that conversation.

Reproduced with the existing `user-demo` owner and `user-partner` editor in the same household:

```json
{"listed":true,"detail_status":404,"detail":{"code":"proposal_not_found"},"continued_status":"failed","continued_code":"proposal_not_found"}
```

This is a chat/command ownership integration mismatch, not a request to weaken confirmation authorization. A read-only conversation that worked becomes inaccessible to another household member as soon as a proposal is present.

Suggested fix: choose one conversation visibility rule and apply it consistently to listing, loading, continuation and proposal projection. If conversations are shared, use an authorized read-only proposal projection that preserves creator-only revise/confirm/cancel authority. If conversations are private, enforce that owner at all conversation entry points. Verify two users within one household and keep cross-household denial and creator-only confirmation checks.

## Verification and limits

From `money-view/`:

```sh
.venv/bin/pytest -q tests/test_platform_chat.py tests/test_platform_chat_model.py tests/test_platform_chat_transport.py --tb=short
```

Result: **24 passed in 6.71 seconds**, with the existing Starlette/AnyIO deprecation warning.

Targeted probe from repository root:

```sh
PYTHONPATH=money-view money-view/.venv/bin/python temp/argus-experience/chat-review-probe.py
```

The probe uses a fresh temporary SQLite database and local TestClient calls. Output is retained in `temp/argus-experience/chat-review-probe.txt`. It makes no model/provider calls.

The reviewed code and passing tests support typed plan validation, a schema that cannot confirm writes, saved-plan resumption, duplicate turn admission, atomic proposal/receipt/transcript callbacks, reset/delete fences, immutable calculation continuation, bounded context/transcript/export paths, and SDK no-retry/client cleanup over mocked HTTP. No additional concrete defect was found on those reviewed surfaces. Membership-generation guards and accepted-logout semantics reuse the existing identity owner. This review does not claim live model quality, browser correctness, production behavior, or exhaustive race coverage.

No app, Git, environment, provider, Supabase, or deployment changes were made. Stop for the assigned fix/review handoff.

## Scoped follow-up: chat-fix package (2026-09-21)

**Current result: one concrete P2 currency residual; the shared-conversation finding is closed.** This follow-up supersedes the earlier two-finding status for the new package.

All seven entries in `review-packages/chat-fix/manifest.json` matched the frozen files and working copies before checks. Reviewed `chat.py`: `e63a06b18c00e20f5ea4731d0614254962fbb0bbc0ad5fe380e739aacee55e15`.

Only the modified currency resolver, read parameter contract, proposal projection, prepared example, export and their tests were reviewed. Unchanged runtime, model prompt and SDK behavior were not reopened.

### Closed behavior

The original explicit DOP read now produces DOP facts; omitted read currency is explicit instead of inheriting USD. The original request-USD/selected-DOP-account calculation now rejects. Shared-household proposal projection loads successfully and permits read continuation while partner revise, confirm and cancel remain denied. Calculation argument continuity remains intact. The prepared goal and bounded immutable export passed their new integration checks, including export of a receipt and more than fifty messages, foreign-household denial, both caps and a pre-reset captured context.

### P2 residual — Include directly selected records in currency resolution

Location: frozen `money-view/server/platform/chat.py:649-662`, with execution at `chat.py:681-702`.

The new resolver verifies only `request.account_id` and `plan.account_id`. A record-read plan can instead select an owned account or transaction through `record_id`; that record's currency never reaches the resolver. `_read_records` then reads the exact record without applying the resolved currency filter. Consequently the supposedly resolved query and the actual money fields disagree.

Both existing record resources reproduce this in a fresh fixture database:

```json
{"resource":"accounts","status":"completed","requested_currency":"USD","query_currency":"USD","returned_currencies":["DOP"]}
{"resource":"transactions","status":"completed","requested_currency":"USD","query_currency":"USD","returned_currencies":["DOP"]}
```

Trigger: request top-level `currency="USD"` with action `{kind:"records", resource:"accounts"|"transactions", record_id:<owned DOP record>}`. The final is successful rather than a currency conflict. This remains within the currency-consistency boundary of the original finding; no unrelated runtime requirement is introduced.

Resolve the selected record through its canonical household owner before finalizing currency/account context, then use that same resolved context for rendering. A conflicting explicit denomination must fail; with no explicit denomination the record's actual currency should be the effective query currency. For transaction records, also preserve the canonical owning account when comparing explicit account context. Keep the existing cross-household lookup protections.

Probe and retained output:

```sh
PYTHONPATH=money-view money-view/.venv/bin/python temp/argus-experience/chat-fix-review-probe.py
```

`temp/argus-experience/chat-fix-review-probe.txt` contains the two lines above. No network/model calls were made.

### Focused verification

From `money-view/`:

```sh
.venv/bin/pytest -q tests/test_platform_chat.py \
  -k 'requested_currency or currency_conflict or selected_account_checks or household_partner or conversation_export or export_rejects or keyless_goal or calculation_followup' \
  --tb=short
```

**16 passed, 13 deselected in 7.12 seconds**; existing Starlette/AnyIO warning only. These checks close the original reproduced branches but do not cover the direct-record residual. No application files were edited. Stopped for the bounded correction and review handoff.

## Reference-final scoped assessment (terminal held for integration delta)

The `chat-reference-final` snapshot is **clean within the assigned reference/currency and SDK transport scope**. The final review is temporarily held at the captain's request for the incoming distinction between display-currency hints and explicit currency. This section is not a terminal approval of that incoming change.

All nine manifest entries matched both the immutable package and working files before testing. Relevant hashes:

| File | SHA-256 |
| --- | --- |
| `chat.py` | `36010666d51235e0172127de77301ec0f210f1aba40b12ce3619e82d016919f9` |
| `commands.py` | `be8e9742a0eb54a10619a64bdd2ba309456a5f899bb6222a9d49e7421c7107f1` |
| `chat_contracts.py` | `2a77189756f5b0c253e984e518aa13b7217cf0bb1dd35c8d1dea0d22272f269a` |
| `chat_model.py` | `6ac14019c6a685843f5132bc7521f59febe88d4b308b221400d33f61474e39b9` |

Both account and transaction `record_id` selections now contribute their canonical owned currency before resolution. Explicit conflicts fail; omitted denomination derives from the owned record. Explicit account-context conflicts and unknown records fail before rendering. `_prepare_execution` holds one read snapshot across reference resolution and read/calculation capture, and closes it before the final write. The concurrent-write test demonstrates a DOP query and DOP fact from the same snapshot even when another thread changes the live account to USD between resolution and capture.

Proposal currency inspection reuses the command owner's normalizer, including inherited revision inputs and authority checks, without performing a domain write. This assessment did not review the five separately assigned command registrations.

The additionally assigned transport review inspected the actual installed adapter and SDK. The SDK's method defaults distinguish `UNSET` (install the SDK retry policy) from explicit `None` (no retry policy). The supplied SDK client prevents LangChain from rebuilding clients. Explicit key/base URL/attribution prevent ambient provider values; both managed HTTP clients use `trust_env=False`; disabled tracing and the non-default quiet SDK logger prevent the reviewed logging/tracing paths. Client context managers close both clients on successful and failed calls. No transport defect was found.

Focused command from `money-view/`:

```sh
.venv/bin/pytest -q tests/test_platform_chat.py tests/test_platform_chat_transport.py \
  -k 'exact_record or share_one_snapshot or calculation_anchor or proposal_record_currency or current_proposal_currency or unknown_selected_account or actual_sdk' \
  --tb=short
```

**37 passed, 30 deselected in 13.64 seconds.** The four SDK cases use mocked HTTP and establish a single attempt for success, 429, 500 and timeout plus cleanup. Only the existing Starlette/AnyIO warning appeared. No live calls or application edits were made. The earlier record-currency residual is closed for this snapshot; await only the captain's specified hint/explicit-currency delta.

## Terminal scoped review — default currency integration

**CLEAN for the assigned chat currency/reference, shared proposal projection, and SDK transport review.** All findings and residuals recorded above are closed for the reviewed snapshots. This terminal result supersedes the earlier open and held statuses. Review is frozen; unchanged code is not reopened.

The captain's immutable `chat-default-final` package and the backend owner's `chat-default-currency` package contain identical backend delta files. All entries checked matched their manifest and working copies. Final relevant SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `chat.py` | `492fd9232e55228ed5f065c4593f8eddb740f72bf2234adc74e030fb2427719b` |
| `chat_contracts.py` | `20ce5c8de0c49868d6fc9ba5fac93e702853cdd86f28de1b93c814830f3913c3` |
| `test_platform_chat.py` | `0fb12add1f7866109a13dcc9f9ba89dbf225b23530edbcfc9e90edcfe059827d` |
| `ConversationPage.tsx` | `8d405811a4dddc7e9717d8714bc13768b0fe8306dc57bbbf50a501be86c0f80e` |
| `stream.ts` | `deb1d2fd607dbd9e2a916e816e3c8fa983de4b98060596c7b5bf8c4e41a792ec` |

The final delta distinguishes `default_currency` from an explicit `currency` claim. The hint participates only after canonical record/account, prior artifact and explicit request/plan constraints have been resolved. Owned and explicit denomination conflicts still reject. Unknown hints fail request validation before a conversation is saved. Missing currency remains explicit when neither a binding source nor a valid fallback exists. Proposal fallback uses the canonical normalizer only after its specific missing-currency result; unrelated validation failures are not swallowed. Generic spending/effective-rate examples no longer embed DOP, while the labeled DOP goal sample retains its explicit denomination.

The captured frontend's `sendText` calls `turnCurrencyContext(currency)` without an action, which emits only `default_currency`. Prepared actions can additionally emit their actual explicit denomination. This code inspection confirms the submitted strong-currency bug is removed in the frozen files. The captain still owns browser/network integration evidence; this review does not substitute for that check.

Focused final command from `money-view/`:

```sh
.venv/bin/pytest -q tests/test_platform_chat.py \
  -k 'ui_default or default_or_verified or currency_hint' --tb=short
```

**16 passed, 59 deselected in 6.71 seconds.** This covers semantic denomination over a display hint, owned-record precedence, three generic examples with/without an account, prior calculation/proposal continuity, explicit conflict rejection, missing proposal currency fallback, and unknown-hint rejection. The earlier **37 passing** reference/snapshot/SDK checks remain valid because this delta does not alter their mechanisms or the transport. Only the existing Starlette/AnyIO warning appeared.

No additional actionable issue was found within the changed boundary. No application edits, Git mutations, live model/provider calls, Supabase access, or deployment were performed. Separate command-registration and browser reviews remain with their assigned owners.
