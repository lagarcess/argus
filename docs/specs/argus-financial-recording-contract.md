# Argus financial recording contract

**Status:** Proposed. The experience rules it cites are founder-approved. This technical contract is not. It is not an implementation assignment.
**Date:** September 28, 2026. Reconciled with the September 28 mobile baseline and the recording decision response.
**Serves:** [MVEE](argus-minimum-viable-ecosystem-experience.md) sections 3, 4, 5 and 12, including the September 27 and 28 subsections on quick account setup, account activity and balance checks, archiving accounts, refunds, financial spaces and connected plan status.
**Fills:** the "financial-record schema, balance/transaction reconciliation model, money arithmetic contracts" gap that [documentation authority](../DOCUMENTATION_AUTHORITY.md) lists as undecided. It answers the obligations in the [account balance reconciliation handoff](argus-account-balance-reconciliation-handoff.md).
**Executable proof:** [`tests/financial_recording/`](../../tests/financial_recording/README.md) and its committed evidence [`docs/reports/evidence/financial-recording/scenarios.json`](../reports/evidence/financial-recording/scenarios.json).

This document recommends one contract for recording money facts. It approves no schema, migration, API route, permission model or chat change. API_CONTRACT, DATA_MODEL and ARCHITECTURE stay authoritative until an approved change amends them.

**Sources and their state.** PR #727 (`codex/native-interface-decision`, head `a1c294319`) publishes the final September 28 mobile baseline, the MVEE sections above, the reconciliation handoff and the [recording decision response](lanes/financial-recording-decision-response.md). It was an open draft when this revision was written. The founder restated the same answers in the lane conversation on September 28, again marking duplicate rows, stale previews and localized categories as recommendations and guest persistence as pending. A later published guest policy states registered accounts for ecosystem features and leaves existing guest chat and quotas unchanged; that is intended direction only. The MVEE, documentation authority and decision log still leave guest/ecosystem access open, so this proposed contract does not close G1 and does not treat that policy as derived from those authorities. Where this document says "approved", it cites the MVEE text published by #727. PR #714's older September 27 sketch is superseded by #727 and is no longer a source here.

## 1. What a person must be able to observe

1. An account has a type, one currency, an optional nickname, and a balance or an unknown balance. Cash is first-class. Vehicles, property and other assets are optional items with an estimated value.
2. A blank balance stays unknown. Argus never shows it as zero, alone or inside a total.
3. A starting balance is not income. Changing an asset's estimate is not income or spending.
4. An expense that already happened is recorded even when the balance on file is short or unknown.
5. Income and spending count only real activity. Transfers between owned accounts and credit-card payments are neither. A refund reduces spending in the month received and is never income.
6. A balance check is a fact. A difference from the recorded amount is shown on the account as an unexplained difference and never counted as income or spending.
7. Activity recorded later and dated on or before a balance check asks whether that check already included it. The answer decides whether it explains the difference or moves the balance. The same money is never subtracted twice.
8. A repeated tap, a retried request or a re-imported file adds nothing. Two real purchases with the same amount both stay.
9. A correction, removal or restore changes every affected account together and keeps its history, including who made it.
10. Archiving an account tidies the account list. Its balance, history and obligations stay in totals.
11. Moving an account to another private space moves no money and rewrites no history.
12. Pesos and dollars never combine, and no exchange rate is ever invented.
13. Home, Accounts, Plan and Updates show the same numbers, because they read the same records the same way, and each discloses what it does not know.

## 2. The model in one paragraph

Argus stores **accounts** and **confirmed records**. A record is either an **anchor**, a known balance at an instant, or **activity**, money that moved. Balances, remaining differences, income, spending and positions are **derived** on read from the current revisions. What a balance check showed when it was confirmed is **kept** on that check's revision and never recomputed. So late information can explain an earlier difference without a compensating entry, and the history still shows what the person saw and accepted. A later performance cache is allowed only if it is rebuilt from the same records. It can never be a second owner and can never erase confirmation-time evidence.

## 3. Accounts

| Field | Rule |
| --- | --- |
| `id` | Server-assigned and stable. Nickname, space and archive changes never change it. |
| `type` | `cash`, `checking`, `savings`, `investment`, `credit_card`, `other_debt`, `property`, `vehicle` or `other_asset` (MVEE quick setup). |
| `nature` | Derived from `type` by one table. `credit_card` and `other_debt` are liabilities. The rest are assets. Never stored. |
| `currency` | One ISO 4217 code (section 4). Locked once the account has any record. |
| `nickname` | Optional. Trimmed. Up to 60 characters. Blank means no nickname, and the client shows the type's localized name. A nickname changes the display name only. |
| `space_id` | The private space that holds the account: Personal by default, or a named Business or Custom space. Household sharing is a separate visibility fact, not a space move. |
| `archived` | Organizational only (section 3.2). |
| `ownership_share_bps` | The person's share of the whole item, 1 to 10,000 basis points. The UI offers All of it, Half, or Another share. Never assume 50/50. Ownership is not permission. |
| `linked_asset_id` | On a debt only. Names the asset it finances. Display only. The debt stays its own account and is counted once. |
| `version` | Increments on every write that touches the account or its records. Used for stale previews and edits (section 8). |

**Type and currency locks.** Currency locks once the account has any record. Type locks once activity touches the account, as the final baseline does ("Keep the currency and account type with their recorded activity"). With only an opening balance, a type change inside the same nature is allowed. A change that flips nature is refused, because it would reverse the meaning of the stored sign.

**Unknown is not zero.** An account has a known balance only after it has an anchor. With no anchor, Argus reports its activity since tracking began instead ("−RD$850 recorded since you started tracking"). Totals follow the same rule. When every asset in a currency is unknown, that currency's assets total is unknown, not RD$0, and so is its net. Liabilities follow the same rule. Unknown accounts are listed in coverage (section 12).

### 3.1 Estimated assets and linked debts

A vehicle, property or other asset records its whole estimated value as its opening anchor, or stays unknown. Its later estimates are `value_estimate` checks. The difference between estimates is labeled a revaluation. It changes position, never income or spending. Personal views count the person's share. A linked loan stays a separate debt with its own share and is counted once. Linking never subtracts the loan a second time. Listing-based valuation remains a future candidate (MVEE, PR #723) and is not needed here.

### 3.2 Archiving and removing accounts

Archiving removes an account from the active list, not from money totals. A non-zero or unknown balance may be archived. Its balance, history and obligations stay in Home and Accounts totals, and coverage lists it as archived and included. Archiving never manufactures an outflow or reduces a debt. Its records stay correctable, and a new entry on an archived account raises only the notice `account_archived`. Restore returns it to the active list. Removing an account is a separate action, allowed only for an empty account. That action is outside this proof and outside the first slice.

## 4. Money

**Representation.** Every recorded amount is an integer count of the currency's minor unit, paired with its currency. Floats never hold a recorded amount. This matches the [payment-ledger assessment](../reports/payment-ledger-reuse-assessment.md).

**Exponent authority.** Argus has no per-currency minor-unit table today. The `currency_fraction_digits` in `web/argus_display_contract/result_display_policy.json` is a backtest display rule, set to 0. It is not a currency's minor unit and must not be reused as one. The repository's currency authority is CLDR through babel, which `src/argus/domain/home_country.py` already uses. Accept a currency only if it is in `home_country.currency_codes()`, then read its exponent with `babel.numbers.get_currency_precision`. Validate first. babel answers 2 for any unknown code, including `XXX`. DESIGN states the same division: currency determines fractional precision, and UI locale determines separators. Do not copy the hardcoded tables of the unmerged `money-view` pilot. Do not reuse the float `Money` in `src/argus/domain/finance/money.py`, which serves calculators.

**Parsing.** Clients normalize locale separators and send a dot-decimal string. More fraction digits than the exponent allows is `amount_precision`. Argus never rounds a person's input.

**Sign.** An account balance is its signed value to the owner. Assets are positive when held. Liabilities are negative when owed. The person types a debt as a positive amount owed, as the baseline does. The server domain is the only place that flips that sign. Clients send what the person typed. A liability above zero is credit in the person's favor and is shown that way.

**Rounding.** Stored amounts are exact, so their sums are exact. Only share-weighted totals round, once each, half up, to the exponent, from exact fractions. A displayed net can therefore differ from displayed assets plus liabilities by one minor unit.

**No combination.** Every total is keyed by currency. Cross-currency transfers stay blocked in the first slice. Combined totals need a display currency and a rate source with date. Neither is approved.

## 5. Records

A record has a **body** and an append-only list of **revisions**.

### 5.1 Anchors: known balances

| Anchor | Meaning | Income or spending? |
| --- | --- | --- |
| `opening_balance` | The balance when tracking began, entered at setup | No |
| `balance_observation`, basis `user_check` | Check balance: "I looked and it said this" | No |
| `balance_observation`, basis `statement` | A statement's opening or closing balance at its date | No |
| `balance_observation`, basis `value_estimate` | A new estimate of an asset's value | No. The difference is a revaluation |

Adding an account with an opening balance completes setup. It needs no second income or expense entry (MVEE). Someone who only knows today's balance records one anchor and nothing else.

### 5.2 Activity: money that moved

The activity **kind** decides the arithmetic. The **category** is optional detail. The baseline presents Income, Expense and Transfer as the type, with source or category as extra detail (MVEE account activity).

| Kind | Source leg | Counter leg | Counts as |
| --- | --- | --- | --- |
| `expense` | −amount | none | spending |
| `refund` | +amount | none | reduces spending, never income |
| `income` | +amount | none | income |
| `transfer` | −amount | +amount on a different account, same currency | neither |
| `debt_payment` | −amount | +amount on a liability, same currency | neither |

Amounts are positive, and the kind supplies the sign. Card interest and fees are expenses. A cash withdrawal is a transfer to cash.

### 5.3 Deciding whether a balance already contains an activity

Every derivation needs one answer: does an anchor's balance already contain a given activity? This rule answers it for each pair of an activity and an anchor on the same account.

1. Activity dated after the anchor is never contained.
2. An explicit answer from the person wins. It is stored on the activity against that one anchor.
3. For a balance check, activity in the check's stored contents is contained. When a check is confirmed, its revision stores the ids of the live activity dated on or before it. That is exactly what its preview showed as the prior recorded amount. Recording order is never used, so activity redated or restored later is asked about, not assumed.
4. Activity from the same source document as the check is contained. A statement's rows do not ask about the statement's own closing balance.
5. For an opening balance, activity dated before its day is contained.
6. Anything else is asked. That covers activity recorded after a check and dated on or before it, including older activity, and untimed activity on an opening's own day.

Anchors are asked in date order, stopping at the first "yes". Once a balance contains an activity, every later balance does too. An explicit "not included" for a later check therefore contradicts an earlier check that contains the activity. That state is refused with `inclusion_conflict` wherever it would arise: confirming a backdated check, answering, redating, or restoring. The person corrects one of the two facts. Argus never picks a winner. So each activity lands in exactly one interval of one account and is counted once. A transfer or payment asks separately for each account leg, because each leg has its own checks. The baseline asks only about the latest check. Asking in date order is the recommended production refinement, because an older entry can predate several checks.

### 5.4 Derivations

- **Balance.** The latest anchor plus every activity that landed after it. With no anchor, the balance is unknown.
- **Remaining difference.** For each check after the first anchor: the observed amount minus the previous anchor and the activity that landed between them. The first anchor on an account has no difference. An unknown prior balance cannot produce one.
- **Recorded difference.** The contents, expected amount and difference the check showed at confirmation, stored on its revision. A correction to the check's own amount or date is a re-confirmation and stores new values on its new revision, keeping the old ones in history. A note edit or a restore carries them forward unchanged.
- **Explained by.** The activities recorded after a check that landed inside it. The history uses this list to show what closed a difference. Argus never labels a difference "resolved" because arithmetic happens to reach zero.
- **Income and spending**, per currency, for a scope and period by activity date. Spending is purchases minus refunds, and both gross figures are reported. A negative net is shown as it is, never clamped to zero. A transfer or payment with one leg outside the scope is reported as moved in or moved out, never as income or spending.
- **Position**, per currency, for a scope: assets, liabilities, net and coverage (section 12).

### 5.5 Worked example: the approved balance check

Opening 10,000 on September 1. Expense 2,000 on September 3. On September 5 the person checks and sees 7,500. The check shows prior recorded 8,000, observed 7,500, difference −500. Confirming saves a labeled balance adjustment.

| Step | Spending | Recorded difference | Remaining | Balance |
| --- | --- | --- | --- | --- |
| Confirm the check | 2,000 | −500 | −500 | 7,500 |
| Record the missing 500 dated September 4, answer "already included" | 2,500 | −500 | 0 | 7,500 |
| Instead answer "changed the balance afterward" | 2,500 | −500 | −500 | 7,000 |
| Instead record only 300, "already included" | 2,300 | −500 | −200 | 7,500 |
| After the first answer, a new 500 dated September 7 (no question) | 3,000 | −500 | 0 | 7,000 |

Correcting the September 3 expense to 2,100 leaves the recorded difference at −500 and moves the remaining difference to −400. Today's balance stays 7,500. Two checks each measure their difference from the anchor just before them.

This is the "explicitly labeled balance adjustment" the MVEE requires. The adjustment is the confirmed check with its recorded difference, not an invented income or expense. The remaining difference is derived beside it, so the history keeps both what the person accepted and what is still unexplained.

## 6. Refunds

| Rule | Proof |
| --- | --- |
| Refunds are money actually returned to cash, checking, savings or a credit card. Other accounts use Check balance. | `refund_account_unsupported` on investment and debt accounts |
| A refund may link its purchase. It is optional. | Linked and unlinked refunds in `refund_unlinked_and_cross_account` |
| A linked refund needs a live purchase, the same currency, a date on or after the purchase and the purchase's category. The refunds linked to one purchase never exceed it. | `refund_purchase_removed`, `refund_link_currency`, `refund_before_purchase`, `refund_category_mismatch`, `refund_exceeds_purchase` |
| A refund may land in another account of the same currency. The destination is the account that received the money. | Card purchase refunded into checking |
| A foreign-currency return is recorded unlinked, in the currency and amount received. No rate is assumed. | USD unlinked refund with negative USD spending, not clamped |
| A card refund reduces the debt and may leave credit in the person's favor. | `card_refund_credit_balance` |
| Removing a purchase with live linked refunds needs review first. Correcting a purchase re-checks every linked refund through the same rule: amount, date, category, currency and kind. A refund is never orphaned silently. | `linked_refunds_present`, and the refund codes above on purchase corrections |
| Loan principal, interest and fee reversals need a breakdown. A generic refund does not guess them. | Refunds on `other_debt` are refused |

## 7. Time and provenance

| Field | Meaning |
| --- | --- |
| `occurred_on` | Local date the activity happened |
| `occurred_at` | Optional instant, when the source gives one |
| `as_of` | Instant an anchor describes |
| `captured_at` | When the source was captured |
| `recorded_at` | Server instant of each revision |
| `recorded_by` | Who made each revision, so either partner can see who recorded or corrected an entry. It grants nothing. |

**Balance date.** The baseline offers "Balance as of", defaulting to today and never in the future. Today means the creation instant. A chosen earlier date means the end of that local day. The person's time zone decides local days. The recommended default is `America/Santo_Domingo`, which has no daylight-saving shift. This is not the New York market clock, which stays unchanged. The zone used is stored with the date, so a later zone change never reinterprets it.

**Changing the balance date, and any edit that moves money.** Editing the opening date is a correction with a new revision and a reason. The same review applies to every correction: an opening date, a check's date, an activity's date or legs. If any activity would move between a balance and a difference, the correction returns `inclusion_changed` with those records. It saves nothing until the person accepts the change after seeing the affected history. If the edit would leave an inclusion question open, on any account it touches or leaves, it returns `inclusion_unanswered` and takes the answer in the same call. A correction that only changes the person's own inclusion answer needs no second acknowledgement. Inclusion answers belong to activity, so a correction or restore of an opening or a check refuses them with `answers_not_applicable`. An opening or a check keeps its account. Recording it on the wrong account is fixed by removing it and recording a new one, so its stored contents always belong to its account. Removing a check that other activity depends on, or restoring a record a later check never saw, follows the same rule. A date change never silently reinterprets existing activity.

**Provenance.** Each revision records a capture method (`manual`, `chat`, `voice`, `document`, `connection`) and a source reference: file digest and row, an institution's `external_id` when printed, or the originating conversation and message. It points at context and never copies raw document text, transcripts or credentials.

## 8. Lifecycle, idempotency and stale previews

| State | Affects totals? | How it moves on |
| --- | --- | --- |
| Draft | No | Capture creates it. Review attaches issues. Editing it raises its revision. |
| Preview | No | Shows effects and records its basis: every touched account's version and the draft revision. |
| Confirmed record, revision 1 | Yes | One confirm call |
| Corrected record, revision n | Yes | `correct(expected_revision, reason, changes)` |
| Removed record | No | `remove(expected_revision, reason)` appends a tombstone |
| Restored record | Yes | `restore(expected_revision, reason, answers)` returns the same record, both legs together, after the same review. A restored activity takes inclusion answers for checks confirmed while it was removed. A restored check takes none, because answers belong to activity. |
| Rejected draft | No | Terminal. Its source is released. |

**Issues.** Blocking issues stop confirmation. The proof's codes are:

- **Input:** `field_missing`, `kind_unsupported`, `amount_invalid`, `amount_precision`, `amount_not_positive`, `currency_unsupported`, `currency_mismatch`, `date_invalid`, `choice_invalid`, `note_too_long`.
- **Accounts:** `account_unknown`.
- **Categories:** `category_unknown`, `category_kind_mismatch`, `category_not_applicable`, `category_other_space`.
- **Linked activity:** `counter_account_missing`, `counter_account_same`, `counter_account_unexpected`, `counter_not_liability`, `cross_currency_unresolved`.
- **Refunds:** `refund_account_unsupported`, `refund_target_invalid`, `refund_purchase_removed`, `refund_link_currency`, `refund_before_purchase`, `refund_category_mismatch`, `refund_exceeds_purchase`, `refund_link_unexpected`, `linked_refunds_present`.
- **Plans:** `expectation_unknown`, `expectation_mismatch`, `expectation_already_fulfilled`.
- **Ordering and repeats:** `inclusion_unanswered`, `inclusion_conflict`, `inclusion_changed`, `already_recorded`, `possible_duplicate`.
- **Spaces:** `account_has_links`.

Notices inform and never block. `negative_asset_balance` flags cash or a bank account below zero, which often means income is missing. `account_archived` flags an entry on an archived account. A short or unknown balance is never an issue. Argus records history. It does not authorize payments.

**Manual saves and batches.** A manual form save runs draft, preview and confirm in one call. It adds no separate AI approval. A statement batch confirms the rows the person selects in one all-or-nothing call. Flagged rows stay held as drafts with their progress. A batch re-reviews each row against the rows confirmed before it. A row that becomes ambiguous inside the batch stops the batch and writes nothing.

**Idempotent confirmation.** Confirm and create carry an idempotency key. The server fingerprints the request with SHA-256 over canonical JSON of the draft ids and reviewed fields. The same key and fingerprint return the original result without a second write. The same key with a different fingerprint is `idempotency_conflict`. An already-confirmed draft returns its record. This reuses the API contract's [idempotency section](../API_CONTRACT.md#contract-idempotency-admission) and the replay-or-conflict pattern in `supabase/migrations/20260722000002_atomic_backtest_admission.sql`.

**Stale previews.** Confirmation succeeds only if the preview's basis still holds. Otherwise it writes nothing and returns `stale_preview` with a refreshed preview. The draft and the person's edits are kept. The person sees the changed effects and confirms again. Two confirmations of one stale preview both fail.

**Stale edits.** Corrections carry `expected_revision`, and account edits carry `expected_version`. A mismatch is `stale_version` and changes nothing. One partner never silently overwrites another's work.

**Correction, not reversal.** A correction keeps the fact at its true date and appends a revision. The payment ledger's reversal postings would move a corrected September expense into October. A record also keeps its currency. A correction may move it only to an account in the same currency.

**Postgres realization (a target, not a migration).** Each confirm runs as one database function in one transaction. It locks the touched accounts, compares their versions to the basis, reserves the key, inserts the record and revision, stores a check's recorded difference, and bumps versions. Every leg commits or none does. The proof runs in memory, so it demonstrates the rules but not the locking.

## 9. Notes

Every financial activity form offers an optional note of up to 200 characters. That includes expenses, income, refunds, transfers, payments and balance checks, including asset value updates (MVEE, DESIGN). The server counts Unicode code points and is the authority. Clients must count the same way. JavaScript `length` counts UTF-16 units and Swift `count` counts grapheme clusters, so neither can be used directly. A note is part of the record's revision. Editing a note is a correction with history. A note never changes money or duplicate matching. Search and partner visibility for notes belong to the search and household contracts.

## 10. Linked activity and plan occurrences

A transfer or debt payment is one record with two legs. Creation, correction, removal and restore act on the record, so one leg never changes alone. Correcting the counter account moves the leg. A card purchase is an expense on the card, and its payment is a `debt_payment`, so spending counts the purchase once.

A plan's dated expectation is fulfilled by at most one live activity, and one activity fulfills at most one occurrence. Status is derived on every read, never stored. The occurrence is completed while a live activity names it with a matching account and kind. It returns to planned when that activity is removed, unlinked, or changed to another account or kind. That kind of change needs review (`expectation_mismatch`). An amount correction keeps it fulfilled. A refund never reopens a paid bill. The forecast excludes fulfilled occurrences, so the payment counts once, in actual cash.

## 11. Duplicates, overlap and late information

1. **Identity.** The same file digest and row, or the same institution `external_id` on the same account, is `already_recorded`. This covers confirmed records, removed records and pending drafts. Re-importing a file or an overlapping statement creates nothing, and a removed row does not return with the next import.
2. **Signature.** Any leg with the same account, amount and date, without shared identity, is `possible_duplicate`. It blocks until the person chooses. "Same as that record" links the new source to the existing record and creates nothing. "Different" saves it. The kind is ignored, so a card statement's payment row meets the payment recorded from checking. Notes are ignored too.

Equal amounts alone never match. The same amount on another account or another date raises nothing. Nothing is merged or deleted automatically. The synthetic kit confirms two identical rows from one file silently. This contract asks once, because a row with no reference cannot prove two purchases happened.

An import row whose destination is ambiguous keeps its account unresolved until the person picks one. Statement balances become `statement` checks, and statement rows answer the inclusion question from their shared source. Late information needs no special operation. The person records the missing activity with its true date and answers the inclusion question.

## 12. Spaces, scopes and what each surface reads

**Spaces.** An account lives in exactly one private space. Moving it to another space is organizational. It creates no record, changes no record, and keeps identity, balance, history, corrections, notes and recoverable removed entries together. Only its scope changes. The baseline blocks a move when the account has links: transfers or payments (including removed ones), cross-account refunds, a linked asset or loan, plan expectations, household sharing, open drafts or statement links. The proof enforces the record, asset, plan, draft and custom-category links and reports them with `account_has_links`. Custom categories belong to a space, so an account whose entries use one cannot leave that space until the category's disposition is reviewed. Household sharing and statement links need the household and ingestion contracts. A cross-space transfer is unresolved and stays out of scope.

**Scopes.** Every derivation takes a scope, meaning the set of account ids the caller may read. The recording model holds no permission logic. Authorization, household membership and RLS decide the scope first. That work is unproved here and belongs to the household contract.

| Surface | Reads | Must disclose |
| --- | --- | --- |
| Home | Position per currency, recent activity, open differences, drafts waiting | "Based on your recorded accounts", unknown accounts, archived accounts included, estimate dates, oldest anchor date |
| Accounts | Balance or unknown, standing (held, overdrawn, owed, credit in your favor), checks with recorded and remaining differences, activity, notes, revisions | Last anchor date and basis. Whether the figure is observed, estimated or derived. |
| Plan | Income and spending by period, expectations and their derived status, forecast of open occurrences | Accounts outside the scope, unknown balances |
| Updates | Events on confirm, correct, remove, restore, or a check that opens a difference | Same scope rules. No amounts in push or email previews. |
| Search | Records and accounts by id with their space | Same scope rules |

**Coverage** is part of every position. It lists known accounts, unknown accounts, archived accounts included, the oldest anchor date and open unexplained differences. A total over partial data is never presented as the whole picture.

**Personal and household.** Personal totals use the person's ownership share. Household totals count each authorized shared account once. Scopes are never added together. A transfer from a private account into a joint account is money moved in from outside the household scope, never household income. The recommended account detail shows the full balance with an explicit personal-share readout. Where ownership data is absent, the production contract must resolve it explicitly rather than assume a share.

## 13. Categories

There is one category owner with stable identifiers. Default categories have fixed ids and localized labels in English and Spanish. Custom categories are allowed in private Business and Custom spaces, approved for Business. Each gets a stable id owned by its space. Renaming changes only the label, so totals keyed by id never move. A custom category cannot be used in another space. The Personal space uses the defaults. Transfers and payments carry no category. Budgets reuse the same owner and never keep a second list.

Creating an account uses no category. A first slice without activity has no category dependency.

## 14. Invariants

| # | Invariant | Scenarios |
| --- | --- | --- |
| I1 | Unknown is never zero, for an account or a total. | `blank_opening_unknown`, `unknown_coverage_disclosure` |
| I2 | Only activity changes income and spending. Anchors, differences, revaluations and refunds-as-income never do. | `clavito_large_opening`, `observation_gap`, `asset_revaluation_and_share`, `refund_unlinked_and_cross_account` |
| I3 | Derived numbers are never stored. A check's contents and recorded difference are stored and change only when the check itself is re-confirmed. | `late_explanation`, `partial_reconciliation`, `backdated_correction` |
| I4 | Each activity lands in exactly one interval per account, decided by date, the check's stored contents, source or an explicit answer. | `older_activity_inclusion`, `two_observations`, `new_expense_after_observation` |
| I5 | Linked legs are one record and change, vanish and return together. | `same_currency_transfer`, `linked_correction_and_removal`, `removal_and_restore` |
| I6 | One currency per record. No netting across currencies. No invented rate. | `cross_currency_transfer_unresolved`, `multiple_precisions`, `refund_unlinked_and_cross_account` |
| I7 | Confirmed facts change only by revisions, each with a reason and author. Removal is a tombstone that keeps identity. | `backdated_correction`, `linked_correction_and_removal`, `notes_across_records` |
| I8 | Drafts affect nothing. | `duplicate_import_vs_twins`, `stale_preview_two_confirms` |
| I9 | Confirmation and creation are idempotent. | `duplicate_submission` |
| I10 | A preview confirms only against the basis it showed. | `stale_preview_two_confirms` |
| I11 | A historical expense is never refused for a short or unknown balance. | `expense_beyond_known_balance`, `overdraft_and_debt` |
| I12 | Equal amounts never establish a match. | `equal_amount_not_a_match`, `duplicate_import_vs_twins` |
| I13 | Integer minor units with a validated CLDR exponent. Input never rounded. Weighted totals round once. | `multiple_precisions`, `asset_revaluation_and_share` |
| I14 | Archive and space moves are organizational. They change no money. | `account_edit_rules`, `unknown_coverage_disclosure`, `spaces_and_account_moves` |
| I15 | Linked refunds never exceed their purchase. A plan occurrence is counted once. | `refund_partial_and_limits`, `plan_occurrence_counted_once` |
| I16 | Scope is an input. The recording model holds no permission logic. | `same_currency_transfer`, `spaces_and_account_moves` |
| I17 | No write moves money between a balance and a difference, or leaves a question open, without review. | `edits_that_move_money_need_review`, `opening_date_correction` |

## 15. Decision table

### Approved experience

| Topic | Source |
| --- | --- |
| Confirmed financial records are durable. See the Decision 8 note below. | MVEE section 4 (#727), decision response 1 |
| Quick setup: type, currency, optional nickname, balance or unknown. Optional assets with ownership share and linked debt. Liabilities entered as amount owed. | MVEE quick account setup, decision log 2026-09-27 |
| Balance date is an editable account detail, and a change must not silently reinterpret existing activity. The correction and review mechanics are this contract's recommendation (section 7). | Decision response 2 |
| Ask whether activity was already included in a checked balance, including older activity and each account leg. Do not ask when provenance already answers. | MVEE balance checks, decision response 3 |
| Unexplained differences stay on the account, labeled, never income or spending. Confirmation-time evidence and remaining differences stay distinguishable. | MVEE balance checks, handoff, decision response 4 |
| Archived accounts keep balances and obligations in totals. | MVEE archiving accounts, decision response 5 |
| Personal views use ownership share. Household counts an authorized account once. Never assume 50/50. | MVEE quick setup and section 12, decision response 6 |
| No implicit FX and no combined-currency total. Cross-currency transfers are blocked in the first slice. | MVEE section 2 and Home summary, decision response 7 |
| Refund semantics in section 6 | MVEE refunds, corrections and adjustments |
| 200-character notes on every financial activity form | MVEE refunds, DESIGN |
| Private spaces, organizational account moves, custom Business categories | MVEE financial spaces and reassigning accounts |
| Plan occurrences counted once, with derived status | MVEE connected plan status |
| Restore returns the original record into its original space and account, with both legs together | MVEE account activity (recovery) |

**Historical Decision 8, corrected.** An earlier version of this contract said Decision 8 kept typed personal figures out of storage. That was wrong. Decision 8 (September 8, 2026, archived grounded-finance roadmap) left typed figures inside conversation messages and put them on the never-store list for personalization memory. The MVEE published by #727 supersedes its prohibition on a new personal-figure storage surface only for explicit financial-record confirmation. Unconfirmed figures keep the existing conversation policy. They are not deleted from chat history, and nothing new enters personalization memory. Guest financial-record persistence remains a separate open decision in the authority docs (G1).

### Recommended engineering choices

| Choice | Recommendation | Alternative rejected |
| --- | --- | --- |
| Storage shape | Accounts and records with append-only revisions. Totals derived. Check evidence stored. | Stored adjustment transactions |
| Inclusion | The section 5.3 rule, asking checks in date order | Asking only the latest check |
| Money | Integer minor units. CLDR exponent after validation. | Floats, or a second currency table |
| Sign | Signed value to the owner, flipped once on the server | Debit and credit columns per type |
| Linked movements | One record with two legs | Two cross-referenced records |
| Undo | Revisions, tombstones, restore of the same record | Reversal postings |
| Retry safety | Key plus fingerprint, reusing admission | Client-side dedupe |
| Concurrency | Account versions as the preview basis. A stale confirm writes nothing. | Last write wins |
| Batches | Hold flagged rows. Confirm selected clean rows all-or-nothing. | Auto-drop equal amounts |
| Stale confirm | Refresh, keep edits, confirm again | Silent acceptance |
| Categories | One owner, stable ids, localized defaults, space-owned custom labels | Fixed-only list |
| Note length | Unicode code points, server authoritative | Each client's native count |

### Still open

| # | Decision | Owner | Recommendation |
| --- | --- | --- | --- |
| G1 | Durable guest financial records / ecosystem access | Founder, pending in MVEE, documentation authority and decision log | Intended direction only: registered accounts for ecosystem features; existing guest chat and quotas unchanged; guests see no accounts surface. Not closed here. |
| G2 | Recovery period, retention and purge for removed entries and accounts | Founder with the data-retention contract | Session-level restore in the baseline only. No invented deadline. |
| G3 | Cross-currency transfer contract (actual amounts on both sides) | Founder, later | Keep blocked. It is separate from unlinked foreign refunds. |
| G4 | Household authorization, RLS, sharing links during moves | Household contract | Unproved here. Do not infer it from ownership. |
| G5 | Partial payment allocation and loan principal, interest and fee breakdown | Later recording contract | Use Check balance until defined. |

PR #727's reconciliation contract also names a "recovery destination" as a founder decision. No published text defines the term. This contract restores into the original space and account, as the MVEE states. G2 covers the period and retention.

## 16. Alternatives rejected and tradeoffs

| Alternative | Why rejected |
| --- | --- |
| Post the difference as an adjustment transaction and rewrite it when missing activity arrives | Two copies of one fact with nothing forcing agreement, the split-brain shape AGENTS.md forbids. Storing the check's evidence and deriving the remainder keeps one owner for each fact. |
| Treat the latest snapshot as authoritative and stop there | The baseline sketch does this in memory. It loses the remaining difference that the handoff requires once later activity arrives. |
| Transplant the payment ledger | SQLite locks, clearing accounts, no identity, and refusal of short-balance expenses (#719). Its money rules and race-test shapes are reused. |
| Full double-entry with equity and suspense accounts | Every opening and difference would need an invisible counter-account. The two-leg record keeps agreement between legs without inventing accounts. |
| Merge on equal amount and date | Collapses real twins such as the kit's `tx-dop-02` and `tx-dop-03`. |

**Tradeoffs accepted.**

- Deriving on read costs work proportional to history since the latest anchor. A rebuildable cache can come later.
- A stale preview costs one extra tap under concurrent use.
- The inclusion question adds friction for late entries dated on or before a check. Guessing would silently move money between a difference and a balance.
- Asking checks in date order can mean more than one question for an old entry.

## 17. What the proof establishes and what it does not

**Establishes.** The rules produce every section 1 behavior on synthetic inputs across 35 named scenarios, including the kit's own CSVs read by `tests.synthetic_ingestion.extract.load_input`. The rules compose without double counting across late answers, corrections, removal and restore, refunds, notes, moves, plan occurrences and duplicate imports. Evidence is committed, and a test fails if it drifts from the model.

**Does not establish.** Postgres locking, RLS and household authorization. Extraction, OCR, speech or model quality. API shape and performance. Link migration during moves beyond refusal. CLDR parity for every code; the proof checks DOP, USD, JPY and KWD, and validates against babel's list because it cannot import `argus`.

**Isolation.** The model lives under `tests/`, imports no `argus` module, and nothing under `src/` or `web/` references it. Tests enforce both.

**How production replaces it.** The expected outcomes are literal values in the tests and the evidence file, and they do not depend on the model code. The scenarios reach the model through the `Scene` helpers in `tests/financial_recording/scenes.py`, the `Store`'s public operations (`create_account`, `edit_account`, `move_account`, `draft`, `edit_draft`, `resolve`, `reject`, `preview`, `confirm`, `confirm_batch`, `correct`, `remove`, `restore`, `create_category`, `rename_category`, `expect`), and the read functions in `derive.py`. That set is the seam. A production PR adds a driver exposing the same names over the real API and database. It runs the scenarios for its slice against that driver, with the same literal outcomes. Both drivers are checked against the literals, never against each other. The reference model is a test oracle, not a production owner. It keeps its full derivation for scenarios whose slice has not landed. Each later slice moves its rules to production and deletes them from the reference model in the same PR. When the checks slice lands, the reference balance derivation goes with it.

## 18. First implementation assignment: create, reopen, edit

**Outcome.** A signed-in person creates an account and later reopens and edits it. Creation takes type, currency, an optional nickname, and a balance or estimate, or unknown. Cash, checking and savings also take an optional balance date. Assets also take an ownership share. Editing covers the nickname, type (until activity exists), ownership share, archive and restore, and the balance or its date through a traceable correction. Nothing else is in scope: no activity, balance checks, categories, transfers, refunds, notes, spaces other than Personal, household, listings, bank connections or chat.

**Dependencies to bind in the assignment, before code.**

1. **Guest policy (G1).** Still open in the authority docs. Intended direction is registered accounts for ecosystem features, with existing guest chat and quotas unchanged and guests seeing no accounts surface. The assignment either waits for those authorities to close G1 or builds that registered-only path behind a default-off flag; do not invent guest financial-record persistence. The flag's release criteria must name the authority close.
2. **API and data ownership.** Amend API_CONTRACT and DATA_MODEL first (Never-Violate 1). Audit SQL and RLS against `postgres-best-practices` (Never-Violate 10).
3. **Opening-date correction behavior.** Adopt section 7. With no activity yet, a date correction reorders nothing, but the revision and reason are still stored.
4. **A database acceptance gate.** Postgres tests for confirm-or-replay, version checks and owner-only RLS, in the `tests/test_*_postgres.py` family CI already gates.

**Owned contracts and production owners.**

| Concern | Owner |
| --- | --- |
| Currency validation and exponent | `src/argus/domain/recording/currency.py`, reading `home_country.currency_codes()` and babel |
| Types, nature table, locks, the single liability sign flip | `src/argus/domain/recording/accounts.py` |
| Opening anchor, revisions, balance derivation | `src/argus/domain/recording/records.py` |
| Persistence | One migration: `financial_accounts` (with `space_id` defaulting to Personal, `archived`, `ownership_share_bps`, `version`) and `financial_records` with `financial_record_revisions`, plus one create-or-replay SQL function. Owner-only RLS on `auth.uid()`. No household columns. |
| HTTP | `src/argus/api/routers/financial_accounts.py`: create with `Idempotency-Key`, read, edit with `expected_version`, and correct the opening with `expected_revision`. OpenAPI regenerated. |
| Client | Per the ARCHITECTURE platform decision. A surface ships only behind the flag above. |

**Acceptance.** Run `clavito_large_opening`, `blank_opening_unknown`, `first_slice_create_reopen_edit` (including its opening-date edit with no activity), `multiple_precisions` and the create part of `duplicate_submission` through a production driver, using the literal outcomes already committed. Add the Postgres gate above. A double-submitted create makes one account. A stale edit returns 409 and changes nothing. An unknown balance never reads as RD$0. An archived account stays in totals.

**No-touch.** Chat runtime, the interpreter prompt and response-schema descriptions (Never-Violate 12). Calculators, simulations and backtest admission. Existing profile columns. Household, invitations, analytics, logging and notifications. `tests/synthetic_ingestion/`. The frozen mobile archive. PR #722's message and stream owner files.

## 19. Existing mechanisms reused

| Mechanism | Where | Use |
| --- | --- | --- |
| CLDR currency set | `src/argus/domain/home_country.py` `currency_codes()` | Currency validation |
| Idempotency grammar and replay-or-conflict | API_CONTRACT `contract-idempotency-admission`, `20260722000002_atomic_backtest_admission.sql` | Create and confirm |
| Revision compare-and-set | `ToolResultCard.input_revision`, the memory `revision` trigger | Stale previews and edits |
| Confirm-once guard | `src/argus/domain/pending_artifacts.py` | Draft consumed once |
| Canonical hashing | `canonical_hash` in `src/argus/domain/backtest_admission.py` | Fingerprints |
| Provenance shapes | `EvidenceArtifact`, `MemoryProvenance`, `ToolFactSource` | Source references |
| Display-contract JSON read by Python and web | `web/argus_display_contract/support_contact.json` pattern | Category catalog labels |
| Synthetic ingestion kit | `tests/synthetic_ingestion/extract.py` `load_input` | Drafts from real CSV bytes |
| Payment-ledger rules (#719) | Minor units, per-currency balance, key plus fingerprint, append-only history, race-test shapes | Adopted as rules. Reversal postings and funds refusal are not. |
