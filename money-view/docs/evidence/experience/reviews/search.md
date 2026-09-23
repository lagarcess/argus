# Omnisearch independent review

Reviewed the immutable package at `temp/argus-experience/review-packages/search/`, its manifest, `search-report.md`, and `search-api.md`. Read current canonical lifecycle and destination code only where needed to validate integration. No application edits, Git operations, external calls, deployment, or Supabase changes.

**Verdict: changes requested. Two P2 findings; no P1 finding.** Both are acknowledged and assigned by the captain. In-flight fixes do not change this snapshot's verdict.

## P2: Derive transaction visibility from the account lifecycle too

Package location: `money-view/server/platform/omnisearch.py:145-161`, specifically the transaction source's `deleted_at IS NULL` predicate at line 149.

Create an account with a transaction, then delete only the account through the existing ledger action. That action sets `p_accounts.deleted_at` and deliberately retains its transactions. Canonical ledger queries hide those transactions by requiring both transaction and account to be active (`ledger._filters`), but Omnisearch still returns their merchant, notes, amount, date, and account target because it only checks the transaction row. The same record is therefore hidden in its owner surface yet exposed as an active search result. The existing deletion test independently deletes both rows and misses this normal lifecycle path.

Use the canonical account lifecycle when selecting transaction candidates, preserving indexed query bounds and correct pagination after filtering. Add a regression deleting only the parent account; restore it to verify the existing transactions become searchable again. Assignment: search worker, coordinated with ledger destination owner.

## P2: Make search navigation resolve the exact record outside default filters

Package location: `money-view/server/platform/omnisearch.py:380-385` and the typed target/query contract in `web/src/features/search/contracts.ts`. Integration locations: `web/src/features/ledger/TransactionsPage.tsx` and `web/src/features/planning/BudgetsPage.tsx`.

Two concrete examples expose one incomplete navigation contract:

- Search an older transaction that is outside its account's first 25 rows. The result supplies `record_id` and `account_id`, but TransactionsPage ignores `record_id` and opens the account-filtered list without selecting or fetching that transaction. A transaction in a different currency can also disappear under the destination's current global currency filter.
- Search a July budget while the budget page defaults to September. The result carries only `record_id`; the page fetches budgets for its current/requested month and merely tries to focus that ID among those rows. The July budget is absent, so opening the result shows an unrelated month without the selected record. Its month is already available in the search preview but is not carried by the target contract.

Resolve owned records at the destination independently of the current list window, or carry the canonical filter context required to load and focus them. Keep typed navigation and ownership checks. Add destination-level regressions for an older transaction, a different-currency transaction, and a budget outside the current month. The existing frontend tests verify serialization of IDs, not whether the destination opens those IDs. Assignment: ledger UI owner for transaction detail and archived-account guard; search worker coordinating budget context.

## Accepted paths and limits

- Every reviewed source query is household-scoped, including conversation message previews and saved-deposit ownership joins. Viewer access is read-only. Conversation state, true chat pins, individually deleted records, and archived planning rows have explicit predicates. Legacy saved flags are not presented as pins.
- User text is bound as a value in indexed ASCII-NOCASE prefix ranges. SQL identifiers come from the fixed source catalog, not the query. Wildcards remain literal. Field candidates, final pages, selected details, and previews are bounded. Multifield matches deduplicate before pagination. The offset ceiling is disclosed without an invalid next link.
- Deposit recall's 500 owned-comparison candidate window is explicitly documented and shown in the UI. It is not represented as exhaustive recall. There is no duplicate text corpus, model invocation, or provider polling.
- Evidence retains source dates and synthetic/user kinds where present; deposit and conversation recall use recording dates without inventing publication dates. Financial values are read from canonical stored fields and minor-unit conversion; search does not invent account balances or holding market values.
- Request sequence guards and aborts protect superseded search reads; query/filter changes reset pagination. Keyboard selection follows grouped display order, uses the input's active descendant, and reserves unmodified Home/End for text editing. The mobile preview transfers focus to Back, hides the result pane, and handles Escape before the modal; shared Modal owns restoration. No additional confirmed defect found in these code paths.
- Exact record targets for new/legacy conversation, saved deposit decisions, and scenario detail have matching destination handling. The two examples above remain the concrete integration gaps.
- Reported verification: 25 backend tests, three frontend helper tests, and TypeScript/Vite build pass. Inspected these tests without rerunning them. Frontend tests exercise helpers, not mounted request races, focus, mobile Escape, or destination behavior. Integrated browser screenshots and interaction acceptance remain with the assigned browser owner; this report does not claim browser acceptance.

Review complete. Only this report was written. Await a frozen fix delta for the two assigned findings; unchanged domains remain closed.

## Scoped recall-fix re-review

Reviewed `review-packages/recall-fix/` and the three fix reports. **Both original functional findings are closed. One P2 residual was introduced by the visibility fix; changes requested for that bounded-query regression only.**

- Transaction visibility derives from `ledger.active_transaction_predicate`, including same-household active account ownership. Search applies it before result LIMIT, so deleted-account children and their pagination hints no longer appear. Restore coverage checks that children return.
- The owned exact transaction endpoint uses the canonical transaction response and active-parent guard. TransactionsPage fetches `record_id` independently of account/currency/list filters, aborts superseded reads, prevents aborted results from opening, provides loading/error recovery, and clears the target when closed.
- The owned exact budget endpoint shares the list projection and rejects missing, archived, and foreign records. BudgetsPage fetches the record, derives the displayed month from it, retains its currency, and focuses the canonical row. Changed-query resource ownership and unavailable-link recovery are present. No additional confirmed destination defect found in these changed paths.

### P2: Bound candidate work when an archived account owns many matching transactions

Fix-package location: `money-view/server/platform/omnisearch.py:302-327`, where the new correlated visibility condition runs before LIMIT against the unchanged transaction field/recent indexes.

Those indexes contain every individually undeleted transaction, including children of archived accounts. When a matching account is archived, SQLite must walk all of its matching transaction entries and check the parent before it can satisfy LIMIT or prove no visible result exists. The result count is bounded, but candidate work is no longer bounded as promised by the API/report and existing query-progress tests. Both broad prefix and empty recent searches are affected. No text corpus synchronization is required to solve this, but the query needs a bounded candidate/continuation design or an equivalent source-owned access path with honest truncation metadata.

Focused diagnostic used an in-memory SQLite database only, the same field index, and the fix's exact household/prefix/visibility/order/LIMIT clauses, projecting just ID:

| Data | Requested limit | Returned rows | Approximate SQLite VM steps |
| --- | ---: | ---: | ---: |
| 10,000 matching transactions, active parent | 21 | 21 | 300 |
| Same transactions, archived parent | 21 | 0 | 130,000 |

The archived case already exceeds the existing test's 10,000-step query budget by 13 times, even with the smaller ID-only projection. Unlike the active fixture, it scans the complete matching account history. The existing scale/index test leaves the large parent active; the new parent-archive regression has only a small history, so neither catches this regression. Add a large archived-parent prefix/recent diagnostic to the same query-budget acceptance surface, while retaining the new visibility, no-leak, and restore assertions.

Reported tests inspected: 27 search, 72 ledger/import, and 35 planning passing. They were not rerun. Only the new isolated in-memory diagnostic was executed; no application data/files were changed. Browser interaction acceptance and the separately ongoing visual/account-target work remain outside this delta review. Only this report was updated; review complete.

## Final scoped search-window review

**Verdict: clean. The archived-history scan residual is closed. No actionable finding remains in the reviewed search fix classes.**

Reviewed the immutable `review-packages/search-window-final/` files and verified every file against its manifest. Current source/test copies matched the package when focused checks ran.

- Each transaction field first selects at most 1,042 indexed IDs, retaining a fixed 1,041-candidate window independent of the requested offset. Only that bounded ID set reaches the canonical active-account visibility check. Candidate-first primary-key lookups prevent the parent filter from walking an arbitrarily long archived history. The IDs and all subsequent reads share one SQLite read transaction; hidden financial fields are not projected before visibility.
- Fixed windows preserve the visible candidate population across page sizes and offsets. Visible rows are sorted/deduplicated as before. `has_more` describes additional visible results within that population; `window_limited` independently discloses excluded candidates. An all-hidden window returns no record IDs/previews and no next-page link, while honestly reporting limited coverage.
- The account source's additive `account_id=id` target is derived from the same scoped row and retains `record_id`. No arbitrary navigation field or extra authority is introduced.
- English and Spanish empty-window guidance explicitly limits the claim to the searched window and suggests a more specific prefix. Nonempty limited results retain that guidance. The changed UI does not claim that excluded history has no matches.

Focused verification executed against the matching source: `python -B -m pytest -q -p no:cacheprovider money-view/tests/test_platform_omnisearch.py -k 'archived_parent_candidate_work or transaction_candidate_window or transactions_follow_account_visibility'`: **4 passed, 26 deselected, 0.43 seconds**. The tests cover prefix/recent archived histories growing from 2,082 to 10,410 rows with fixed VM work, hidden-record absence and truthful limited metadata, mixed visible/archived pagination, and archive/restore behavior. One existing Starlette/AnyIO deprecation warning was emitted. Unchanged suites and browser matrices were not rerun.

Exact reviewed SHA-256 hashes:

| Package path | SHA-256 |
| --- | --- |
| `money-view/server/platform/omnisearch.py` | `39740794c7809dbae8bd4b934ddbb73a85a50154cde7447f29863f512a43ff80` |
| `money-view/tests/test_platform_omnisearch.py` | `d390d8ac7db65024ffa85ecd1a98be62b550437825782ec83c53a93033b2ac78` |
| `money-view/web/src/features/search/Omnisearch.tsx` | `9d96ebe6b6db627334cea000e5f33b6f867b2e330b745c057202fc178d36cfff` |
| `money-view/web/src/features/search/copy.ts` | `af70bbf3d6ce63635c41c81ce47df8e0fc19ada0f42de19f4c161e016f60d190` |
| `money-view/web/src/features/search/search.css` | `8159b05e3447e3ac5e823e1fe16451c5498c8aec10722867c5b61025f2f815dd` |

Review is finished and frozen at these hashes. Only this report was edited; no application or Git changes. No active follow-up retained.
