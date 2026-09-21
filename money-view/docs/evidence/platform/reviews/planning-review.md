# Planning review

Reviewed the supplied `planning-review.diff` against `money-view/docs/PLATFORM_PLAN.md` and `docs/platform-api/planning.md`, with current ledger and Store helpers read only for integration context.

**Spec compliance: changes requested. Code quality: changes requested.** Two bounded issues below; no confirmed scenario-formula, reservation-capacity, payment-atomicity, or household-isolation defect found in the reviewed paths.

## Findings

### P2: Reject non-expense categories before saving bills and budgets

Location: `money-view/server/platform/planning_contracts.py:20-23`.

The validator accepts every key in the ledger category map, including `income` and `transfer`. An editor can therefore create a valid USD bill for 90 with either category. Saving succeeds, but paying it always raises `invalid_category`: `planning.py:241` posts an expense, and the canonical ledger requires its category to map to `expense` (`ledger.py`, `_validate_categories`). The bill remains unpaid until edited. The same accepted categories produce budgets whose actual spending stays zero, because the canonical spending query includes only expenses/refunds. Check the category's mapped kind at the planning boundary, deriving allowed expense categories from the existing canonical map. Add a parameterized input-boundary regression for both non-expense categories, covering bills and budgets.

Evidence is a complete static request-to-ledger trace; no existing tests were rerun. The snapshot contains the same membership-only validator.

### P2: Page saved scenario lists before loading full monthly receipts

Location: `money-view/server/platform/planning.py:320-322`.

`GET /scenarios` selects every saved document and deserializes each complete receipt, including its monthly result series. Each valid 100-year receipt contains 1,200 monthly rows, so 100 saved versions return 120,000 monthly rows in a single response; ordinary 30-year receipts still return 36,000 rows at that count. Saving comparisons continually grows this response with no bound. This conflicts with the platform plan's explicit server-side pagination requirement and makes reopening the scenario list progressively expensive. Add bounded pagination to this list and its handoff contract; the existing single-receipt endpoint can supply full details as needed. The shared plan lists are also unpaged, but full scenario histories amplify the same issue most strongly.

## Verified design and limits

- The calculator uses effective annual return/inflation converted to monthly rates, fees of annual_fee_pct/1200, explicit beginning/end cash flows, funded withdrawal capped at available balance, visible shortfall, and first zero-balance withdrawal month as depletion. Allowed rates keep the monthly growth/fee factors positive. Real balances discount by the elapsed monthly inflation factor. No conflicting formula was found.
- Goal allocation checks current ledger balances, currency, and other active reservations inside `BEGIN IMMEDIATE`; replacement excludes the goal's prior allocation and commits atomically. Archived goals release capacity. Subsequent spending and unavailable accounts remain visible as underfunding.
- Bill payment inserts its canonical ledger transaction, occurrence receipt, and next date in one write transaction. Same-date payment replay returns the existing receipt; schedule-advance failures roll back all writes. Budget actuals derive from canonical ledger spending, including category splits/refunds through that owner.
- Scenario receipts have no edit route and a database UPDATE guard. Household lookup predicates and editor guards are present on the reviewed mutation paths. Lifecycle clearing preserves the seed manifest.
- Implementation-provided evidence: 23 focused tests passed in 0.77 seconds. This review inspected that suite and did not rerun it. Exact numerical assertions cover zero flows, growth, inflation, and depletion; fee/timing checks are directional rather than a numerical oracle. The two findings above are not covered. Broad UI, lifecycle composition, load testing, and provider work were outside this review.

No implementation edits, Git operations, provider calls, environment changes, or server/deploy work performed. Review complete; no active follow-up retained.

## Scoped fix re-review

Reviewed only `temp/money-platform/planning-review-fix.diff` and direct call sites affected by the changed scenario-list contract.

**Verdict: clean for the reviewed fix delta. Both P2 findings are closed. Spec compliance and code quality pass within this bounded backend/contracts/tests scope.**

- Category validation now requires the canonical category map's value to be `expense`. Parameterized regressions cover every currently non-expense category for both bills and budgets, without introducing another category catalog.
- Scenario lists now apply household-scoped SQL LIMIT/OFFSET with a default of 20 and maximum of 100, return total/page metadata, and remove monthly/yearly series in SQL before deserialization. A household index supports the lookup. Count and page reads share a read transaction. Full receipt lookup and immutable persistence are unchanged.
- Added tests cover page ordering across multiple pages, household isolation, compact summaries, full selected-receipt preservation, empty pages, and invalid page bounds. HTTP coverage verifies query handling and viewer access. The API handoff explicitly describes the summary/detail distinction and page controls.
- No new reachable backend defect found in this delta. Backend callers do not depend on the removed list-series fields. UI page/detail adaptation remains separately owned and was not claimed verified here.
- Implementation-provided evidence is now 31 passing focused tests; this re-review inspected the changes without rerunning the suite. Earlier unchanged-path coverage limits remain descriptive, not new blockers.

Only this report was changed. Scoped re-review complete; no active follow-up retained.
