# Scoped import review

## Final latest-delta rereview: import-sequence

Verdict: **CLEAN for the reviewed ordered-identity delta. Both prior P2 findings are closed; no concrete residual found.** Scope was the new `statement_identity.py` resolver, its use in ledger preview/commit, and the new regression cases, compared with the previously reviewed `import-fix` package. No unchanged frontend or unrelated domain scope was reopened.

Frozen package: `temp/argus-experience/review-packages/import-sequence/`. All three current file hashes matched its manifest before verification:

- Ledger: `c7b54e3f7de415c22a94c07e0f55882c656dab01ab868c719b7965e3eb9f8b9a`.
- Identity resolver: `fed6b1ec764200161636c66bccc7789e737a9f7669addbc46101752e332eea23`.
- Statement tests: `14e1dcfd4af6d188563c7f8b22364e998c3cef93115a30ad0a0e84372f98e7bc`.

The fix puts ordered identity classification in one pure resolver. Candidate ancestry is reserved independently of retained writes, so the user's skip decision cannot turn a frozen exact descendant into an import. Preview identity version/status/ancestry/match snapshots are covered by the existing digest. Confirmation reruns that resolver under the existing writer transaction; explicit skips and frozen exact rows remain nonwrites, while relevant newly persisted matches invalidate intended imports. Source-ID lineage is stored only for rows actually imported. Distinct known IDs, same-source conflict detection, receipt replay and prior-policy preview refresh retain clear behavior.

Fresh independent focused verification: **19 passed, 36 deselected**, 1.75 seconds, one existing Starlette/AnyIO deprecation warning. Selection covered repeated-source groups for prior and same-file unidentified ancestors, both import/skip decisions, all generated mixed sequences, a new unknown match after review, previous-policy preview refresh, original unknown-provenance cases, concurrent recheck, distinct bank IDs and immutable duplicate choices. The generated resolver tests exercise 243 sequence/baseline combinations and their valid choices; route tests additionally verify retained lineage, receipt replay and subsequent preview truth. The worker's broader **97 passed** result is recorded in `import-sequence-report.md`; I did not repeat that broader suite.

This is a scoped code-review clearance, not browser or release acceptance. No application files, Git state, production, Supabase, environment, provider or deployment actions were changed during rereview.

## Previous delta rereview: import-fix

Verdict: **original sequential/race defect fixed; one residual P2 in the same duplicate-decision policy**. Reviewed `temp/argus-experience/review-packages/import-fix/` against the original package. All six current file hashes matched the frozen manifest before reproduction. Ledger SHA: `012c870e3e2bdddd6a87dcce65f62ff652610c183ff0a2a21912e3fd0dc2bc10`.

The shared `_requires_duplicate_review` policy correctly distinguishes positively identified matches from unknown provenance for prior unmapped statements, manual transactions, legacy imports and concurrent inserts. Existing distinct bank IDs remain distinguishable. The original two-import reproduction is closed.

### P2: An in-file exact duplicate can resurrect a skipped source identity

**Locations:** fixed `money-view/server/platform/ledger.py:728-734` and `:797-813`.

Preview marks a repeated source ID exact even if its earlier occurrence requires a user decision. Commit adds source IDs only when actually inserting, so skipping the earlier occurrence makes the repeated row lose its exact status. With no matching transaction in the pre-commit baseline, that row is silently imported despite being displayed as an exact duplicate that would be skipped.

**Reproduced:** use an empty matching ledger history, statement mode and date/merchant/amount/source-ID mapping for:

```csv
Date,Merchant,Amount,Reference
2026-09-20,Repeated bank ref,-8.25,
2026-09-20,Repeated bank ref,-8.25,bank-ref-1
2026-09-20,Repeated bank ref,-8.25,bank-ref-1
```

Preview returns line 2 `new`, line 3 `possible`, line 4 `exact`. Confirm with the only required decision, `{line:3, action:"skip"}`. Actual receipt: **imported 2, duplicates 1**. Expected: imported 1, duplicates 2. This is the UI's ordinary “skip all possible duplicates” path, not a malformed request. If the unidentified match already exists before preview, the related repeated-source case returns `import_preview_changed` instead of honoring the skip because the later exact row unexpectedly reaches the baseline guard.

**Correction:** make the persisted preview's duplicate identity groups and review decisions govern every occurrence through commit. A repeated exact occurrence must not become importable because the earlier occurrence was intentionally skipped. Retain the separate transaction-time guard for genuinely new concurrent matches. Avoid fixing only the displayed badge or adding a special third-row condition.

**Needed regression:** parameterize an unidentified match already persisted versus earlier in the same file, repeated same-source rows, and import/skip decisions. Confirm skip writes none of that source group, import writes it once, exact rows stay skipped, and retries retain the same receipt. Keep mixed-order/distinct-ID/race rollback tests green.

Fresh rereview verification: statement-import plus ledger suite **72 passed**, one existing Starlette/AnyIO deprecation warning, 2.42 seconds. The residual was reproduced separately against the same frozen runtime; it is not covered by those tests.

### Exact transaction target delta

No additional actionable finding established in the new canonical transaction GET and shared active-account predicate. The route remains household scoped and returns canonical response/splits/evidence independently of list page/currency. React cancels obsolete target requests and guards completions; modal Back handling lives in the shared modal owner. The assigned browser worker still owns actual delayed-target, cancellation and visual execution evidence. Static review alone is not browser acceptance.

## Original review record

Original verdict: **one P2 correctness finding; fix before acceptance**. Reviewed the frozen package at `temp/argus-experience/review-packages/imports/`, its manifest and implementation handoffs. The four reviewed server files' current SHA-256 values matched the frozen manifest before reproduction. No implementation or Git changes were made.

## P2: Adding a source-ID mapping bypasses review for previously unidentified transactions

**Location:** `money-view/server/platform/ledger.py:700-705`, with the same policy gap at `:768-774` during commit.

`possible = not source_id and ...` treats every previously unseen incoming bank ID as proof of a new transaction, even when the matching ledger transaction has no source identity. A normal user can import a file without mapping its optional reference column, then reimport the same file with that column mapped. The second preview says “new,” requires no duplicate decision, and confirming it posts the same expense again. The same class affects transactions imported through legacy CSV or recorded manually, and a concurrent no-source import can pass the commit-time guard because that guard also excludes incoming rows with source IDs.

**Reproduced against the frozen runtime:** create an isolated local Store and authenticated fixture context; import the CSV below with date/merchant/amount mapping; confirm; preview the exact same bytes with `source_id: Reference` added; confirm again.

```csv
Date,Merchant,Amount,Reference
2026-09-20,Review duplicate,-8.25,bank-ref-1
```

Observed output:

```json
{"first_imported":1,"second_status":"new","second_review_count":0,"second_imported":1,"same_file_digest":true}
```

Both confirmations returned receipts. The source ID was absent from the first transaction's lineage, so there is no evidence that the two entries represent different purchases. The issue changes balances and spending, not just a duplicate badge.

**Smallest safe correction:** make duplicate classification distinguish identified matches from matches with unknown source provenance. A positively identified different bank ID can preserve an otherwise identical purchase. An unidentified matching transaction still requires explicit possible-duplicate review, even when the incoming row has an ID. Use the same classification owner for persisted matches, in-file matches and the transaction-time recheck. Do not globally reject every content match: the existing distinct-bank-ID behavior is useful and must remain.

**Required verification:** parameterize sequential matches from an unmapped statement, legacy import and manual entry; verify possible-review and explicit import/skip outcomes. Cover a matching unidentified transaction arriving between preview and commit, including rollback if an earlier row in that commit was already inserted. Preserve tests for two known distinct bank IDs, exact replay, changed source content and concurrent confirmations. Include mixed identified/unidentified rows within one file so the rule does not depend on row order. If skipping an unidentified match deliberately does not bind the new source ID, keep subsequent reviews explicit rather than silently inventing lineage.

## Verified scope and remaining limits

- Shared parser bounds count attempted logical rows, including malformed/blank rows, and cap UTF-8 bytes, columns and cell sizes. Strict quote/control checks, exact decimal/date choices and typed transaction validation form a coherent boundary. File content remains inert data.
- Statement preview/commit correctly scopes the account and import to the household, rechecks role/generation and active account, rejects expired/uncommittable previews, binds the persisted preview digest, and stores the transaction writes, lineage, receipt and idempotency record in one transaction. Replay decisions are checked. Account currency is immutable through the existing AccountPatch contract.
- Holding-import changes reuse the shared parser before database access and retain canonical holding validation and atomic writes. No additional changed-path finding was established. Existing broader holding lifecycle behavior was not reopened by this parser-only review.
- Static React review found file-read epochs for file replacement/paste/unmount, disabled request-time controls, guarded response handling, retained confirmation idempotency key, explicit duplicate decisions and bilingual mapping choices. No additional reachable frontend defect was established. Browser races and visual acceptance were not executed in this review.
- Focused fresh test run: `money-view/.venv/bin/python -m pytest -q -c money-view/pytest.ini money-view/tests/test_platform_statement_import.py money-view/tests/test_platform_investing_imports.py` — **51 passed**, one existing Starlette/AnyIO deprecation warning, 2.28 seconds. The new duplicate-provenance reproduction passes through a gap in those tests.

Applied pstack boundary discipline/root-causes and Argus review proportionality: one shared policy defect, no speculative unrelated requirements. No production, deployment, Supabase, environment, provider or live-model actions.
