# Argus financial recording contract

**Status:** Proposed. Not founder-approved. Not an implementation assignment.
**Date:** September 27, 2026.
**Serves:** [MVEE](argus-minimum-viable-ecosystem-experience.md) sections 3 (Home, Accounts, Plan, Updates), 4 (one destination for every capture method), 5 (shared ingestion and trust requirements), and 12 (household facts without duplicate money).
**Fills:** the "financial-record schema, balance/transaction reconciliation model, money arithmetic contracts" gap that [documentation authority](../DOCUMENTATION_AUTHORITY.md) lists as undecided.
**Executable proof:** [`tests/financial_recording/`](../../tests/financial_recording/README.md) and its committed evidence [`docs/reports/evidence/financial-recording/scenarios.json`](../reports/evidence/financial-recording/scenarios.json).

This document recommends one contract for recording money facts. It does not approve a schema, a migration, an API route, a permission model, or a chat change. The existing API contract, data model, and architecture stay authoritative until a founder-approved change amends them. Section 13 lists the choices only the founder can make.

## 1. What a person must be able to observe

These behaviors come from the MVEE. The contract is the smallest model that produces all of them.

1. An account has a nickname, a type, and one currency. Cash is a first-class type.
2. A blank starting balance stays unknown. Argus never shows it as zero.
3. A large starting balance is not income.
4. An expense that already happened is recorded even when the balance on file is short or unknown. Argus records history. It does not execute payments.
5. Income and spending count only real activity. A transfer between owned accounts is neither. A credit-card payment does not count the card's purchases twice.
6. A balance the person checks is a fact. When it disagrees with recorded activity, Argus shows the difference and never invents activity to hide it.
7. Information supplied later can explain an earlier difference without subtracting the same money twice.
8. A repeated tap, a retried request, or a re-imported file adds nothing. Two real purchases with the same amount both stay.
9. A correction or removal changes every affected account together and keeps its history.
10. Pesos and dollars never combine silently.
11. Home, Accounts, Plan, and Updates show the same numbers, because they read the same records the same way, and each discloses what it does not know.

## 2. The model in one paragraph

Argus stores **accounts** and **confirmed records**. A record is either an **anchor** (a known balance at an instant) or **activity** (money that moved). Every other number is **derived** on read: balances, the difference an observation reveals, income, spending, net position, and coverage. Nothing derived is stored. That rule makes late information work. The difference a balance check reveals is recomputed from the records every time, so a missing expense supplied later shrinks that difference automatically, and no compensating entry exists to undo.

The rest of this document defines each piece.

## 3. Accounts

| Field | Rule |
| --- | --- |
| `id` | Server-assigned, stable. |
| `nickname` | Required. Trimmed. 1 to 60 characters (the approved sketch's limit). A blank name is refused, never replaced by a default such as "My account". |
| `type` | One of `cash`, `checking`, `savings`, `investment`, `property`, `credit_card`, `loan`, `other_debt`. |
| `nature` | Derived from `type` by one table. `credit_card`, `loan`, and `other_debt` are liabilities. The rest are assets. Never stored. |
| `currency` | One ISO 4217 code per account (section 4). Immutable once the account has any record. |
| `archived` | Boolean. Archived accounts keep their history. New drafts cannot target them. |
| `ownership_share_bps` | The owner's share of the account, 1 to 10,000 basis points. Default 10,000. This is ownership, not permission (section 11). |
| `version` | Integer. Increments on every write that touches the account or its records. Used for stale-preview detection (section 8). |

**Type changes.** A type change inside the same nature is an ordinary edit. A change that flips nature (checking to credit card) is refused once the account has a record, because it would reverse the meaning of every stored sign. The person archives the account and creates the right one.

**Unknown is not zero.** An account has a known balance only after it has an anchor. With no anchor its balance is `unknown`, and Argus reports the activity recorded since tracking began instead ("−RD$850 recorded since you started tracking"). An unknown balance is excluded from totals and listed in coverage (section 10).

**Archive.** Archived accounts leave position totals and are listed separately in coverage. Their past activity still counts in historical income and spending, because that money really moved. Whether Argus warns before archiving an account with a non-zero or unknown balance is founder decision F5.

## 4. Money

**Representation.** Every recorded amount is an integer count of the currency's minor unit, paired with the currency code. Floats never hold a recorded amount. This matches the payment-ledger assessment ([#719](../reports/payment-ledger-reuse-assessment.md), for issue 716).

**Exponent authority.** Argus has no per-currency minor-unit table today. The existing `currency_fraction_digits` in `web/argus_display_contract/result_display_policy.json` is a display rule for backtest results (it is 0). It is not a currency's minor unit and must not be reused as one. The repository's currency authority is CLDR through babel, which `src/argus/domain/home_country.py` already uses for the code set. Recommendation: a currency is accepted only if it is in `home_country.currency_codes()`, and its exponent is `babel.numbers.get_currency_precision(code)`. Validate first. babel returns 2 for any unknown code, including `XXX`, so reading the exponent of an unvalidated code silently invents precision. The proof checks this trap. Do not copy the hardcoded tables in the unmerged `money-view` pilot (`currency_minor_digits()`), and do not reuse the float `Money` in `src/argus/domain/finance/money.py` for recorded amounts. That type serves calculators.

**Parsing.** User and import input arrives as a decimal string. More fraction digits than the exponent allows is a review issue (`amount_precision`). Argus never rounds a person's input. `1500.5` JPY is an issue. `1.234` KWD is 1,234 minor units.

**Sign convention.** One rule, with no per-type branching: an account balance is its signed value to the owner. Assets are positive when held. Liabilities are negative when owed. A card that owes RD$3,000 has balance −300,000 minor units. An overdrawn checking account is negative. The entry form still asks for the amount owed as a positive number, as the approved sketch does, and converts at the boundary. This avoids the payment ledger's inverted debit/credit convention, which #719 warns would flip balances if copied.

**Rounding.** Stored amounts are exact, so sums of them are exact. The only rounding happens when a total is weighted by ownership share. That total is computed with exact fractions and rounded once, half up, to the currency exponent, at the reader.

**No combination.** Every total is keyed by currency. No function sums two currencies. Cross-currency transfers and converted totals are unresolved (founder decisions F7 and F8). Argus never invents a rate.

## 5. Records

A record has a **body** and an append-only list of **revisions**. There are two families of body.

### 5.1 Anchors: known balances

| Anchor | Meaning | Changes income or spending? |
| --- | --- | --- |
| `opening_balance` | The balance when tracking began. `as_of` defaults to the account's creation instant and is editable. | No. |
| `balance_observation`, basis `user_check` | "I looked and it said this." | No. |
| `balance_observation`, basis `statement` | A statement's opening or closing balance at the statement's date. | No. |
| `balance_observation`, basis `value_estimate` | An estimated value of an asset such as a car, a property, or holdings. | No. The difference is a revaluation. |

A person who only knows today's balance records one anchor and nothing else. That satisfies MVEE 4.1 ("record that fact without inventing a complete transaction history").

### 5.2 Activity: money that moved

Activity **kind** decides the arithmetic. **Category** is a label the person chooses. They are separate fields. "Income" is a kind. "Salary" and "remittance" are income categories. A category is valid only for the kinds a catalog table allows. A mismatch is the blocking issue `category_kind_mismatch`. The approved sketch presents "Income" as a category next to Groceries and Dining. Under this contract that choice becomes the income kind.

| Kind | Source leg | Counter leg | Counts as |
| --- | --- | --- | --- |
| `expense` | −amount | none | spending |
| `refund` | +amount | none | reduces spending |
| `income` | +amount | none | income |
| `transfer` | −amount | +amount, a different account, same currency | neither |
| `debt_payment` | −amount | +amount, which must be a liability, same currency | neither |

Amounts are positive. The kind supplies the sign. Card interest and fees are expenses with categories such as `interest` or `fee`, which increase the amount owed. A cash withdrawal is a transfer from checking to cash. Later cash purchases are expenses (MVEE section 3).

### 5.3 Derivations

- **Balance at time t.** Take the latest anchor with `as_of` at or before t. If none exists, the balance is unknown. Otherwise add every activity effect placed after that anchor and at or before t.
- **Observation gap.** For each observation, subtract the previous anchor plus the activity between the two from the observed amount. The first anchor on an account has no gap. It establishes the balance. A `value_estimate` gap is labeled `revaluation`. Every other gap is labeled `unexplained`.
- **Income and spending** for a scope and period, per currency. Spending is expenses minus refunds. Income is income. Transfers and debt payments are excluded. A transfer or payment with exactly one leg inside the scope is reported as `moved_in_from_outside_scope` or `moved_out_of_scope`, never as income or spending. Anchors, gaps, and revaluations never enter income or spending.
- **Position** for a scope, per currency. It reports assets, liabilities, and net over accounts with a known balance, plus coverage (section 10).

### 5.4 Worked example: the observed balance

Opening 10,000 on September 1. Expense 2,000 on September 3. On September 10 the person checks and sees 7,500.

| Step | Records | Spending | Gap at Sept 10 | Balance now |
| --- | --- | --- | --- | --- |
| Check balance | opening, expense, observation | 2,000 | −500 unexplained | 7,500 |
| Supply the missing 500 dated Sept 7 | + expense 500 before the check | 2,500 | 0 | 7,500 |
| New 500 expense dated Sept 12 | + expense 500 after the check | 3,000 | 0 | 7,000 |
| Instead, supply only 300 dated Sept 7 | + expense 300 before the check | 2,300 | −200 | 7,500 |

The balance after the check follows the observation, because the bank is the better witness to what the account held on September 10. Known spending is never inflated to absorb the gap. The late 500 is subtracted once. It lands before the observation, so it explains the gap instead of lowering the balance.

A backdated correction behaves the same way. Changing the September 3 expense from 2,000 to 2,100 moves the gap from −500 to −400 and leaves today's balance at 7,500. Two successive observations each measure their gap against the anchor immediately before them, so activity between them affects only the later gap.

## 6. Time and provenance

Each record carries separate times. The MVEE requires Argus to distinguish the activity date, the statement or as-of date, and the capture time (section 5).

| Field | Meaning |
| --- | --- |
| `occurred_on` | Local calendar date the activity happened. Required for activity. |
| `occurred_at` | Optional instant, when the source gives one. |
| `as_of` | Instant an anchor describes. A statement closing balance uses the end of its local day. |
| `captured_at` | When the source was captured (a photo, an import, a message). |
| `recorded_at` | Server instant of the confirming write. Every revision has its own. |

**Local day.** A person's local dates use their time zone. Recommended default: `America/Santo_Domingo`, which has no daylight-saving shift. This is not the New York market clock in `src/argus/domain/market_data/new_york_clock.py`, which owns market dates and stays unchanged. Where a per-person time zone lives is part of the first slice's profile dependency.

**Same-day ordering.** Activity with only a date, on the same local date as a timed observation, is ambiguous. The draft gets the blocking issue `observation_order_unknown`, and review asks whether the balance the person saw already included it. The answer is stored as `same_day_order: before | after`. The two answers give different, correct results. Argus does not guess, because the guess decides whether the entry explains a gap or lowers the balance. Founder decision F3 covers the question's wording and when it appears.

**Provenance.** Every revision records its capture `method` (`manual`, `chat`, `voice`, `document`, `connection`) and a `source_ref`. For an import that is the file digest and row, and an `external_id` when the institution prints a reference. A chat draft points at its conversation and message, following the existing `EvidenceArtifact` and `MemoryProvenance` precedents. Source references point at context. They do not copy raw document text, transcripts, or credentials into the record (MVEE section 5, privacy).

## 7. Lifecycle

Every capture method feeds one operation. The MVEE path is capture, interpret or extract, review and resolve, confirm, save, update dependent surfaces.

| State | Affects balances or totals? | How it moves on |
| --- | --- | --- |
| `draft` | No. | Capture creates it. Review attaches issues. |
| `draft` with blocking issues | No. | The person resolves each issue or rejects the draft. |
| `preview` | No. | Shows the draft's effects and records the basis it was computed on (section 8). |
| `confirmed` record, revision 1 | Yes. | One confirm call. |
| Corrected record, revision n | Yes, as the latest revision. | `correct(expected_revision, reason, changes)`. |
| Removed record | No. History kept. | `remove(expected_revision, reason)` appends a tombstone revision. |
| `rejected` draft | No. | Terminal. |

Issues carry a severity. **Blocking** issues stop confirmation: `amount_precision`, `unsupported_currency`, `invalid_date`, missing fields, `category_kind_mismatch`, `counter_account_missing`, `cross_currency_unresolved`, `account_archived`, `observation_order_unknown`, `already_recorded`, and `possible_duplicate`. **Notices** inform and never block: `negative_asset_balance` tells the person that cash or a bank account would fall below zero, which often means income is missing. A short or unknown balance is never a blocking issue.

A manual form save is the person's confirmation. MVEE 4.1 forbids an extra AI approval step, so a manual save runs draft, preview, and confirm in one call. A statement batch confirms the selected previews in one all-or-nothing operation. Flagged rows stay drafts and do not hold back the reliable rows (MVEE 4.4).

**Correction instead of reversal.** A correction appends a revision with a reason, and derivations read the latest revision. The payment ledger undoes a payment by posting a linked reversal at a new time. For personal records that would move a corrected September expense into October's spending. A revision keeps the corrected fact at its true date and keeps the full history.

## 8. Idempotency, stale previews, and concurrent writes

**Idempotent confirmation.** A confirm call carries an idempotency key. The server fingerprints the reviewed body as the SHA-256 of canonical JSON.

- The same key with the same fingerprint returns the original record, with no second write.
- The same key with a different fingerprint is `idempotency_conflict`.
- Confirming a draft that is already confirmed returns its record.
- Account creation follows the same rule, so a double tap creates one account.

This reuses the existing Argus pattern. `Idempotency-Key` grammar and `(user_id, operation_scope, key)` reservation are in the API contract's [idempotency section](../API_CONTRACT.md#contract-idempotency-admission). The replay-or-conflict hash comparison lives in `supabase/migrations/20260722000002_atomic_backtest_admission.sql`.

**Stale previews.** A preview records a basis: the `version` of every account it touches and the draft's revision. Confirmation succeeds only if that basis still holds. Otherwise the call returns `stale_preview` with a fresh preview and writes nothing. Two confirmations of the same stale preview, whatever their keys, both return `stale_preview`, and neither writes. The person sees the refreshed effects and confirms once. The model follows `ToolResultCard.input_revision`, which returns `409 tool_result_changed` today, and the confirm-once guard in `src/argus/domain/pending_artifacts.py`.

**Corrections and edits** carry `expected_revision` or `expected_version`. A mismatch is `stale_version` and changes nothing. One partner's correction therefore never silently overwrites the other's (MVEE section 12).

**Realization in Postgres (not a migration).** The confirming write runs as one database function in one transaction. It locks the touched account rows, compares their versions to the preview basis, reserves the idempotency key, inserts the record and its first revision, and bumps each touched account's version. Every leg of a linked record commits or none does. The proof runs in memory, single process. It demonstrates the rules, not Postgres locking (section 15).

## 9. Linked activity

A transfer or a debt payment is **one record with two legs**, not two records that point at each other. Creation, correction, and removal act on the record, so one leg can never change without the other. Correcting the amount changes both legs. Changing the counter account removes the leg from the old account and adds it to the new one. Removal takes both legs away and keeps the history.

A credit-card purchase is an `expense` on the card. The later card payment is a `debt_payment` from checking to the card. Spending counts the purchase once. The payment moves money between the person's own accounts.

Both legs must share one currency. A peso-to-dollar movement gets the blocking issue `cross_currency_unresolved`. Section 13 lists the options (F7). The proof never computes a rate.

## 10. Duplicates, overlap, and late information

Two tests decide whether a new draft repeats an existing record.

1. **Identity.** The same file digest and row, or the same institution `external_id` on the same account, means the draft is `already_recorded`. Re-importing a file or an overlapping statement creates nothing new.
2. **Signature.** The same account, currency, amount, date, and kind without shared identity means `possible_duplicate`. This blocks the draft until the person chooses. **Same as that record** links the draft's source to the existing record as extra provenance and creates nothing. **Different purchase** saves it.

Equal amounts alone never match. The same amount on another account or another date raises no issue at all. Nothing is ever merged or deleted automatically (MVEE section 5, duplicates). A spoken entry later seen on a statement follows the signature path. The statement row becomes provenance on the spoken record, so the purchase counts once.

A statement's opening and closing balances become `statement` observations at the statement's dates, and its rows become activity. Section 5.3 then reconciles the statement against itself and against earlier anchors. Imported balances and imported rows never add together as new money (MVEE 4.4).

Late information that explains an old difference needs no special operation. The person records the missing activity with its true date, and the derived gap shrinks (section 5.4).

## 11. What each surface reads

Every surface calls the same three derivations: balance, income and spending, and position with coverage. They take a **scope**, which is a set of account ids the caller is authorized to read. The recording model contains no permission logic. Authorization chooses the scope before the derivation runs.

| Surface | Reads | Must disclose |
| --- | --- | --- |
| Home | Position per currency, recent activity, open gaps, drafts waiting for review | "Based on your recorded accounts", unknown accounts, the oldest anchor date |
| Accounts | Per-account balance or unknown, anchors with gaps, activity, provenance, revisions | The last anchor's date and basis, and whether the figure is observed or derived |
| Plan | Income and spending for the period, per currency, and contributions as transfers into goal accounts | Accounts outside the scope and unknown balances |
| Updates | Events emitted when a record is confirmed, corrected, or removed, or when an observation creates or clears a gap | The same scope rules. No amounts in push previews (MVEE section 3) |
| Search | Records and accounts by id, linking to their owner surface | The same scope rules |

**Coverage** is part of every position. It lists accounts with a known balance, accounts with an unknown balance, archived accounts left out, the oldest anchor date, and open unexplained gaps. Home must never present a total over partial data as the person's whole picture.

**Personal and household.** A joint account is one account. It can sit in a personal scope and a household scope, and it counts once in each. Argus never adds two scopes together. A transfer from a private account into a joint account is `moved_in_from_outside_scope` in the household view, never household income (MVEE section 12).

**Ownership share is not permission.** `ownership_share_bps` says how much of an asset or debt belongs to the person. It never decides who may view or edit a record. The proof values a view two ways, full and owner share, and applies the same weighting to assets and debts. A 50% share of a RD$1,000,000 car and a 50% share of its RD$400,000 loan give RD$300,000 in the owner-share view and RD$600,000 in the full view. The founder picks the default view (F6). Household membership, invitations, who may edit a shared record, revocation, and RLS belong to a separate household contract (MVEE section 9) and are not designed here.

## 12. Invariants

The proof checks each invariant through the named scenarios in [`scenarios.py`](../../tests/financial_recording/scenarios.py).

| # | Invariant | Scenarios |
| --- | --- | --- |
| I1 | Unknown is never zero. | `blank_opening_unknown`, `unknown_coverage_disclosure` |
| I2 | Only activity changes income and spending. Anchors, gaps, and revaluations never do. | `clavito_large_opening`, `observation_gap`, `asset_revaluation_and_share` |
| I3 | Derived numbers are never stored. Every surface reads the same derivation. | `late_explanation`, `partial_reconciliation`, `backdated_correction` |
| I4 | A balance is the latest anchor plus the activity after it. | `new_expense_after_observation`, `two_observations`, `same_day_order` |
| I5 | Linked legs are one record and change together. | `same_currency_transfer`, `credit_card_purchase_then_payment`, `linked_correction_and_removal` |
| I6 | One currency per record. No cross-currency netting. No invented rate. | `cross_currency_transfer_unresolved`, `multiple_precisions` |
| I7 | A confirmed fact is never edited in place. Revisions append. Removal is a tombstone. | `backdated_correction`, `linked_correction_and_removal` |
| I8 | Drafts affect nothing. | `duplicate_import_vs_twins`, `stale_preview_two_confirms` |
| I9 | Confirmation is idempotent by key and fingerprint, and by draft. | `duplicate_submission` |
| I10 | A preview confirms only against the basis it showed. | `stale_preview_two_confirms` |
| I11 | A historical expense is never refused for a short or unknown balance. | `expense_beyond_known_balance`, `overdraft_and_debt` |
| I12 | Equal amounts never establish a match. Identity or the person's choice does. | `equal_amount_not_a_match`, `duplicate_import_vs_twins` |
| I13 | Amounts are integer minor units with a validated CLDR exponent. Input is never silently rounded. Weighted totals round once. | `multiple_precisions`, `asset_revaluation_and_share` |
| I14 | Scope is an input. The recording model holds no permission logic. | `same_currency_transfer`, `unknown_coverage_disclosure` |

## 13. Decision table

### Already approved experience (MVEE and existing rules)

| Topic | Source |
| --- | --- |
| Accounts include cash, checking, savings, investments, credit cards, other debts. Cash is first-class. | MVEE section 3 |
| Nicknamed accounts, balance per currency, manual activity, corrections, reconciliation against statement or observed balance | MVEE sections 3, 4.1 |
| All capture methods converge on capture, review, confirm, save. Drafts affect nothing. A manual save is the confirmation. | MVEE sections 4, 4.1, 5 |
| Transfers are not spending. A card payment never counts purchases twice. Balance changes never manufacture income or spending. | MVEE section 3 |
| Never invent activity to force agreement. Distinguish a correction from a new transaction. | MVEE section 5 |
| DOP and USD are separate. No silent combination. A future conversion shows rate, date, and source. | MVEE section 2, Wave 1 rule R2 |
| Activity date, as-of date, and capture time are distinct. Old balances stay old. | MVEE section 5 |
| Uncertain duplicates go to review. Legitimate similar purchases are never deleted silently. | MVEE section 5 |
| Joint account is one account. Private-to-joint transfers are not household income. Membership is not permission. | MVEE section 12 |
| Liabilities are entered as a positive amount owed. | Approved sketch, PR #714 |

### Recommended engineering choices (this proposal)

| Choice | Recommendation | Main alternative rejected |
| --- | --- | --- |
| Storage shape | Accounts plus confirmed records with append-only revisions. Everything else derived. | Stored reconciliation adjustments (section 14) |
| Money | Integer minor units. CLDR exponent through babel, validated against `home_country.currency_codes()` first. | Floats, or a second hand-written currency table |
| Sign | Signed value to the owner. Liabilities negative. | Debit/credit columns per account type |
| Kind vs category | Kind drives arithmetic. Category is a validated label. | Category-only, as the sketch shows |
| Linked movements | One record, two legs | Two records cross-referenced |
| Undo | Revisions and tombstones | Reversal postings |
| Retry safety | Idempotency key plus body fingerprint, reusing the existing admission pattern | Client-side dedupe only |
| Concurrency | Per-account version as preview basis. `stale_preview` writes nothing. | Last write wins |
| Matching | Identity, or the person's explicit choice | Amount and date heuristics that merge automatically |
| Short balance | Record it, with a notice for a negative asset | The payment ledger's `InsufficientFundsError` |

### Unresolved user-visible choices for the founder

| # | Decision | Recommendation |
| --- | --- | --- |
| F1 | Decision 8 (2026-09-08, archived grounded-finance roadmap) keeps typed personal figures out of storage. Does the MVEE supersede it for **confirmed** records, while unconfirmed chat figures stay ephemeral? | Yes. Record the supersession in the decision log before any migration. |
| F2 | Opening balance date: fixed to account creation, or editable to an earlier date? | Default to creation, editable. |
| F3 | Same-day ordering question: wording, and whether to ask or assume. | Ask only when a same-day observation exists. "Was this already included in the RD$7,500 you saw?" |
| F4 | How an unexplained difference appears, and whether a person can mark it resolved without adding activity. | Show it on the account with "Add what's missing" and "Leave as unexplained". Never count it as spending. |
| F5 | Archiving an account whose balance is non-zero or unknown. | Allow it with a warning that the balance leaves totals. |
| F6 | Default view of shared ownership: full balance or owner's share. | Account detail shows the full balance. Personal totals use the owner's share. Household totals count the shared account once, in full. |
| F7 | Cross-currency transfer (DOP to USD). | Until an FX policy exists, let the person state both amounts and show the implied rate as theirs. Never fetch or invent one. The proof keeps this blocked. |
| F8 | Any combined-currency total. | None until F7 and a rate source are decided. |
| F9 | A possible duplicate inside a statement batch. | Confirm the reliable rows. Hold the flagged ones as drafts. |
| F10 | A stale preview at confirm time. | Re-show the refreshed effects and require one more tap. |
| F11 | Category catalog: fixed, editable, or user-created, with Spanish and English labels. | Fixed bilingual catalog for the first release. |
| F12 | Guest persistence of accounts. | Registered users only for the first slice. Guest persistence stays parked (MVEE section 9). |

Household permission mechanics are **not** in this table. The MVEE parks them (section 9), and they need their own contract.

## 14. Alternatives rejected and tradeoffs

| Alternative | Why rejected |
| --- | --- |
| **Store a reconciliation adjustment** (−500 "balance adjustment" at the check, as many trackers do) | When the missing 500 arrives later, spending would subtract it twice unless something rewrites the adjustment. That is a second copy of one fact with nothing forcing agreement, the split-brain shape AGENTS.md forbids. Deriving the gap avoids it. |
| **Transplant the payment ledger** | #719 found SQLite locks, clearing-pool account types, no user or household identity, and a refusal to record a short-balance expense. Its money rules, retry proof, and concurrency test shapes are reused. The service is not. |
| **Full double-entry with equity and suspense accounts** | Every opening balance and every gap would need an invisible counter-account. People see accounts, not journals. The two-leg record keeps the useful property, that linked legs always agree, without inventing accounts. |
| **Treat the latest observation as the only truth and discard activity before it** | Spending history and late explanations would be lost. Anchors keep both. |
| **Reject an expense beyond the known balance** | Argus records history. A refusal drops a real expense (#719, MVEE section 1.1). |
| **Merge on equal amount and date** | Two real RD$125.50 purchases at one store would collapse into one. The synthetic kit's CSV twins `tx-dop-02` and `tx-dop-03` exercise exactly this. |

**Tradeoffs accepted.**

- Deriving on read costs computation that grows with an account's history. Scanning from the latest anchor bounds it. A cache may come later only as a rebuildable projection, never as a second owner.
- Rejecting stale previews adds one extra tap under concurrent use. It is rare for one person and protects partners from overwriting each other.
- Blocking same-day ordering adds a question. It appears only when a same-day balance check exists, and a wrong guess would silently shift money between a gap and the balance.
- Revisions keep more rows than in-place edits. The history is what lets Updates explain changes (MVEE section 5, corrections).

## 15. What the proof establishes and what it does not

**Establishes.** Under synthetic inputs, the proposed rules produce the observable behaviors in section 1. That covers each scenario in section 12, including the kit's own CSVs read through `tests.synthetic_ingestion.extract.load_input`. The rules are consistent with one another. Late explanation, corrections, linked removal, stale previews, and duplicate imports compose without double counting. The committed evidence file equals the model's regenerated output, and a test fails if they drift.

**Does not establish.**

- **Postgres behavior.** The model is a single in-memory process. Row locks, RLS, and concurrency under real transactions need their own tests against the chosen store, following the three race-test shapes #719 names.
- **Extraction or interpretation quality.** Drafts come from authored inputs and the kit's CSV parser. No OCR, speech, model, or bank data is involved. #720 lists what a real Dominican statement must show first.
- **API shape, performance at scale, or UI.**
- **Household permission.** Scopes are passed in.
- **CLDR parity with ISO 4217 for every code.** The proof checks DOP, USD, JPY, and KWD. The proof validates codes against `babel.numbers.list_currencies()` because the reference model cannot import `argus`. Production validates against `home_country.currency_codes()`.

The reference model lives under `tests/`, imports no `argus` module, and is referenced by nothing under `src/` or `web/`. Tests enforce both properties. It cannot become a second production ledger without a deliberate move.

## 16. First implementation proposal (not authorized)

**Outcome.** A registered person creates an account, saves a starting balance or leaves it blank, reopens the account, and edits its details. Nothing else: no activity, no observations, no chat, no household, no import.

**Dependencies before any code.** Founder answers F1, F2, F11 (types only), and F12. API_CONTRACT.md and DATA_MODEL.md amended first (Never-Violate 1). SQL and RLS audited against `postgres-best-practices` (Never-Violate 10). An assigned package names the owner.

**Intended production owners.**

| Concern | Proposed owner |
| --- | --- |
| Currency exponent and validation | `src/argus/domain/recording/currency.py`, reading `src/argus/domain/home_country.py` and babel. The one owner, projected to web by extending `scripts/generate_home_country_codes.py` if the client needs exponents. |
| Account types, nature table, account rules | `src/argus/domain/recording/accounts.py` |
| Anchor records, revisions, balance derivation | `src/argus/domain/recording/records.py` and `derive.py` |
| Persistence | A new Supabase migration: `financial_accounts`, `financial_records`, `financial_record_revisions`, and one confirm-or-replay SQL function. Owner-only RLS (`owner_id = auth.uid()`). No household columns. |
| HTTP | A new router `src/argus/api/routers/financial_accounts.py`: create with `Idempotency-Key`, read, edit with `expected_version`. Schemas beside the existing ones. OpenAPI regenerated. |
| Client | Deferred to the platform decision in ARCHITECTURE.md. A web surface ships behind a default-off flag if assigned. |

**Acceptance.**

- Create "Clavito" (savings, DOP) with RD$250,000.00. Reopen it and see RD$250,000.00 known, with income RD$0.
- Create an account with a blank balance. Reopen it and see "unknown", never RD$0.
- A double-submitted create with one key makes one account. The same key with a different body returns `409 idempotency_conflict`.
- A rename with a stale `expected_version` returns 409 and changes nothing. A currency change after the opening is saved is refused.
- Correcting the opening balance appends a revision and never touches income.
- `amount_precision` for extra decimals, and an unknown currency refused before its exponent is read.
- Postgres tests for the confirm-or-replay function and owner-only RLS, in the `tests/test_*_postgres.py` family CI already gates.
- The scenario `first_slice_create_reopen_edit` in this proof, re-expressed against the real API.

**No-touch.** Chat runtime, interpreter prompt, and response-schema field descriptions (Never-Violate 12). Calculators, simulations, and backtest admission. Existing profile columns, except reading the time zone if F2 needs it. Household, invitations, analytics, logging, notifications. `tests/synthetic_ingestion/`. The mobile sketch in PR #714.

## 17. Existing mechanisms reused

| Mechanism | Where | Use here |
| --- | --- | --- |
| CLDR currency set | `src/argus/domain/home_country.py` `currency_codes()` | Currency validation |
| Idempotency key grammar and replay-or-conflict | API_CONTRACT `contract-idempotency-admission`, `20260722000002_atomic_backtest_admission.sql` | Confirm and create |
| Revision compare-and-set | `ToolResultCard.input_revision`, memory `revision` trigger in `20260729225600_add_personalization_memory_persistence.sql` | Stale preview and `expected_revision` |
| Confirm-once guard | `src/argus/domain/pending_artifacts.py` `consume_pending_artifact` | Draft consumed once |
| Canonical hashing | `canonical_hash` in `src/argus/domain/backtest_admission.py` | Body fingerprint |
| Provenance shapes | `EvidenceArtifact`, `MemoryProvenance`, `ToolFactSource` | `source_ref` and capture method |
| Synthetic ingestion kit | `tests/synthetic_ingestion/extract.py` `load_input` | Drafts from real CSV bytes in the proof |
| Payment-ledger rules (#719) | integer minor units, per-currency balance, key plus fingerprint, append-only history, race-test shapes | Adopted as rules. Reversal postings and funds refusal are not. |
