# Scoped investing review

Verdict: changes requested. Two P2 findings, no P1 findings.

Read-only review of `server/platform/investing.py`, `market_data.py`, `market_job.py`, their focused tests, and `docs/platform-api/investing.md`. No implementation changes, test execution, Git actions, services or external provider calls. Reproduction sequences below are derived from the inspected code, not claimed as executed tests.

## P2: Fractional order rounding can create fictional cash at an unchanged price

- **Location:** `money-view/server/platform/investing.py:1142-1152`, settling through `confirm_order`.
- **Class owner:** The shared paper-order settlement calculation (`_build_order_legs` and cash/position confirmation), not individual symbols or UI controls.
- **Reproduction:** With the seeded AAPL price of USD 230, preview and confirm a buy of `0.00006` shares using a fresh preview/key. Its exact value is USD `0.0138`, rounded to a USD `0.01` debit. Preview and confirm two sells of `0.00003` shares each, with fresh previews/keys. Each exact value is USD `0.0069`, rounded to a USD `0.01` credit. The position is empty again, the price never changed, and cash increased by USD `0.01`. Every quantity meets the public eight-decimal quantity contract. An even smaller purchase can currently add shares for zero cash.
- **Impact:** Ordinary supported fractional orders can manufacture simulator profits through independent rounding. Receipts are atomic but preserve financially inconsistent cash movements.
- **Fix direction:** Define one settlement rule that prevents splitting or aggregating fractional orders from creating cash. Apply it across symbol, bundle and recurring orders. Merely rejecting zero-gross orders does not fix the nonzero reproduction above. Add a buy/split-sell round-trip check at unchanged prices, plus the sub-minor-unit boundary.

## P2: A recovered recurring run can still settle after being marked interrupted

- **Location:** `money-view/server/platform/investing.py:2024-2035`; recovery at `_reconcile_recurring_run` lines 1791-1804.
- **Class owner:** Recurring-run authority at the paper-order transaction boundary.
- **Reproduction:** Start a recurring attempt and pause worker A after its `still_running` read succeeds but before `confirm_order` obtains its write transaction. After the 30-second domain lease, replay the same plan with worker B. B observes no receipt, marks the run `failed` with `recurring_run_interrupted`, advances the plan, and returns that failed result. Resume A before the five-minute preview expires. `confirm_order` checks the quote and cash but never checks the recurring run status, so it writes a receipt and changes cash/positions despite the failed run. A's reconciliation then changes that same run back to succeeded.
- **Impact:** Recovery can report a terminal no-order failure and advance the schedule while a stale attempt remains authorized to move fictional cash. The existing crash tests cover an abandoned record and an already-confirmed receipt, but not an overlapping old worker resuming after recovery.
- **Fix direction:** Check the recurring run's settlement authority under the same SQLite write transaction that commits its receipt and cash change. Preserve reconciliation of receipts that genuinely committed before recovery. Cover the above two-worker interleaving without sleeping or provider work; the operational job queue need not be redesigned.

## Other inspected boundaries

No additional actionable findings in household scoping, linked-account versus manual-asset net-worth ownership, reset deletion order/manifests, ordinary confirmation idempotency, or provider execution boundaries. The Alpaca adapter uses its fixed market-data GET destination; browser loads use only fixtures. The bounded recurring due query and creator-role check are present, and manual runs intentionally use the current editor's authority. Existing root-level portfolio snapshot work was treated as accepted scope and not reopened.

## Scoped fix re-review: clean

Both P2 findings are addressed in the inspected fix. No new actionable findings within the settlement and recurring-authority delta.

- **Rounding:** `_settlement_minor` owns buy-ceiling/sell-floor settlement and rejects exact gross below one minor unit. Symbol and bundle legs both call it; recurring purchases flow through the same preview/confirmation path. Preview and receipt carry the exact nonnegative `rounding_cost`. The frontend validates both new fields and displays the exact string in previews, confirmations and order history. The fractional round-trip test covers a nonzero rounded buy followed by split sells; sub-minor buy/sell cases, bundles and recurring receipts are also covered.
- **Recovery:** `confirm_order` checks the supplied recurring run's current status, active plan, book and plan/period idempotency key while holding the same SQLite write transaction that mutates cash/positions and writes the receipt. Receipt replay remains before that guard. The former detached `still_running` read is gone. The new controlled interleaving test recovers the run immediately before old-worker settlement and checks that the failed state remains, no receipt appears and cash/positions stay unchanged. Existing receipt-first recovery coverage remains.

The worker reports 24 investing tests passed, Ruff/diff-check clean and the UI build passed. This re-review inspected the changed code and tests; it did not rerun tests or call providers. Scope is the two original findings and their fixes; this is not a fresh whole-module or browser acceptance claim.
