# Ledger review

Verdict: **clean within the assigned ledger scope**. No concrete, reachable defect requiring a change was found in `ledger-review.diff` against `money-view/docs/PLATFORM_PLAN.md` and `money-view/docs/platform-api/ledger.md`.

## Spec and correctness

- Account balances derive from opening minor units plus posted, nondeleted transactions. Both single-account and account-list queries scope the account and its transactions to the same household. Overview consumes that account query directly. Negative balances reduce net worth, including credit-card and loan balances; no currency conversion or cross-currency summation occurs (`ledger.py:107–145`, `461–484`).
- Income and spending use the shared ledger-lines view. Splits replace their parent allocation, retain the original signed total, and contribute only their matching category amount to category-filtered aggregates. Refunds reduce spending. Pending entries, transfers, and adjustments do not enter income/spending. Reversals negate the original amount and splits on the original effective date, and both sides become immutable (`ledger.py:257–266`, `321–337`, `422–442`).
- Transfers validate both household-owned accounts and their currency, insert equal opposite entries within one write transaction, and delete/restore the pair together. Shared write helpers allow the caller's business operation and the ledger command receipt to roll back atomically (`ledger.py:347–369`, `395–407`).
- CSV preview validates headers, row shape, currency, money precision, category, and transaction signs. Commit rechecks account-specific content fingerprints under the write lock and stores its receipt in that transaction. Repeated command keys and repeated import commits return stored receipts; conflicting command payloads fail. Export neutralizes formula-like user text and caps output (`ledger.py:92–104`, `294–313`, `555–630`).
- Failed simulated sync preserves `last_good_at` and does not change accounts or transactions. Transaction and account pages are SQL-bounded with stable ID tie-breaks; aggregates cover the full filter. Amount sorting requires one currency (`ledger.py:147–155`, `269–286`, `542–550`).
- Household predicates cover public reads, mutations, imports, private exports, and lifecycle helpers. Viewer mutations are rejected. Private lifecycle helpers explicitly leave authorization to their caller (`ledger.py:635–652`).

## Investing composition

Read-only inspection of the current investing helper confirms that overview calls `net_worth_additions` once using the same SQLite read transaction and household context. That helper selects active, household-owned manual holdings and returns their priced totals by currency. It reads neither linked ledger balances nor simulated trading cash/positions. Linked investing account reads themselves derive from `ledger.account_balances`. Thus linked account balances appear once, and separately valued manual assets appear once (`ledger.py:463–483`; `investing.py:646–712`).

## Evidence and limits

Accepted the supplied evidence without rerunning unchanged tests: **22 passed in 1.08 seconds**, **13,680 transactions across 24 months, 14 demo accounts, and four currencies**; reported transaction page **12 ms**, overview **11 ms**, and spending **0.82 ms**. Inspected the acceptance tests and implementation statically. This report does not independently reproduce those timings or establish browser, composed-application, CI, or deployment readiness. No code, Git, environment, provider, or server changes were made.
