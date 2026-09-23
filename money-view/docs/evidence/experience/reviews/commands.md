# Frozen command implementation review

## Verdict

The conditional `TransactionBoundStore` implementation removes the transaction
boundary objection from the earlier design review for the 23 registered,
synchronous handlers. It is a constrained compatibility facade, not an
unexamined proxy: `Store.transaction()` begins the only `BEGIN IMMEDIATE`;
nested domain `connection()` scopes receive the same restricted connection and
cannot commit; the outer `Store` scope alone commits or rolls back.

I traced the registered ledger, planning, investing, credit, tax/estate, and
memory closures. They use the bound store synchronously. The facade rejects
transaction/DDL/PRAGMA/attach operations and raw cursor capabilities, poisons
the unit of work on SQL/fetch/nested-scope failure even when subsequently
caught, rejects cross-thread use and callbacks/handlers that return awaitables,
and prevents a real event-loop yield from committing. The receipt, proposal
consumption, canonical write, and transcript callback share that outer scope.
The existing authority guard runs inside it; stored generation and role are
compared before pending execution; dependencies are reread and fingerprinted;
and consumed replay returns the immutable receipt before any writer or callback.
The focused test design corroborates those paths, but this conclusion follows
from the actual facade and handler closures rather than test count alone.

## P1 finding: `tax.scenario` has no canonical receipt target

`tax.scenario` is registered as a confirmed command, but its canonical handler
only calculates and returns a result; it does not create a scenario record.
`CommandService.confirm()` therefore falls through to `proposal_id` as
`record_id` ([commands.py](../../../../server/platform/commands.py#L977-L979)).
It then emits that value in both the receipt target and query
([commands.py](../../../../server/platform/commands.py#L1006-L1018)). The card
always navigates using `receipt.record_id` ([cards.tsx](../../../../web/src/features/chat/cards.tsx#L298-L306)).

This ID names neither an organizer nor a tax item. `TaxOrganizer` recognizes
only organizer/item IDs when restoring selection and retains the calculation
only in component state ([TaxEstatePage.tsx](../../../../web/src/features/services/TaxEstatePage.tsx#L35-L50)). Opening the receipt thus lands on Tax with a nonexistent record ID and cannot reopen the confirmed calculated artifact. This conflicts with the plan's same-artifact continuity requirement and the package claim that receipt targets use canonical record IDs.

Resolve it before accepting `tax.scenario` as a registered confirmed command:
either persist a canonical immutable tax-scenario artifact that the target can
identify, or model the receipt as conversation-only and omit the fictitious
record target. Do not make the UI silently reinterpret a proposal ID as a tax
record.

No other reachable failure was found in the requested transaction, authority,
currency, dependency, expiry, replay, or callback-rollback surfaces.

## Follow-up review: resolved

The scoped fix resolves the P1 finding. `tax_scenario()` now snapshots the
owned organizer, ordered source items, stated rate, calculation result, and
evidence into `p_tax_scenarios` within the caller's transaction. The scenario
has its own `tax-scenario-*` ID; the command confirmation rejects any handler
without a real result ID, so a proposal ID can no longer become a fictitious
artifact target. The immutable-update trigger, household-scoped detail route,
bounded organizer history, export/clear/usage ownership, and UI hydration all
refer to that same ID. A later tax-item change produces a different saved
worksheet while the original result remains readable, which preserves the
reviewed source snapshot.

`read_for_conversation()` is proportional to the shared-conversation problem:
it checks current household read authority and exact conversation membership,
then projects a proposal without creator filtering. It is used only after the
chat owner has read the household-scoped conversation. `get`, `current`,
`confirm`, `revise`, and `cancel` still use the creator-scoped lookup, so the
new projection does not grant a household collaborator write authority.

No residual reachable finding was identified in the changed tax-artifact or
shared-read boundaries. The earlier transaction-facade conclusion remains
unchanged; no Store change was introduced.

## Frozen capability-delta review: clean

Reviewed immutable package `command-capabilities-final` at these verified
SHA-256s:

- `money-view/server/platform/commands.py`:
  `8748c43756192e11cb34e5b789fe095657a576f1666de3c92781a07a2c54fc6b`
- `money-view/server/platform/command_contracts.py`:
  `934fa48f2fc425fbf860fbf103f73b3a173d2ed9d3ee811341c94c6ad701f4b1`
- `money-view/tests/test_finance_commands.py`:
  `6d17b92fd2ceb169e40c59bfb3199156fda613ddfe2d44613d473db9a843b3d4`

The five additions use their canonical, synchronous owners through the already
reviewed bound-store facade. `tax.item.create` derives currency and dependency
truth from the owned organizer. Estate document and checklist creation write
their existing estate records. `investing.recurring.create` rereads the owned
simulation book (and its optional fixed bundle), enforces matching currency,
creates only a recurring fictional-plan record, and exposes the explicit
`scheduled_paper`, `real_money=false` terms. It neither creates a recurring run
nor an order at confirmation. Its receipt points to the resulting recurring
plan, which the investment surface can focus.

`bill.payment.record` derives the account/currency from the referenced bill,
delegates occurrence and ledger mutation to `planning.record_occurrence`, and
then targets the actual canonical transaction. Repeating a new proposal for
the same due date returns the existing paid occurrence and transaction; it does
not record a second payment or reduce the balance again.

`inspect_currency` and `inspect_revision` are read-snapshot operations. They
reuse `_normalize` and the same parent/reference/currency validation as prepare,
do not create a proposal or receipt, and preserve creator-only authority for a
revision inspection. No actionable defect was found in the requested delta.
