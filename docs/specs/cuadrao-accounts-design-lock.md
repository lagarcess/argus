# Cuadrao Accounts: approved interaction decisions

Status: founder-approved design direction, locked September 30, 2026.
Applies to the Cuadrao native design canvas. This is not a financial API contract,
a shipped-capability claim, or authorization to replace the connected client.

The founder approved preserving the previous evening's Accounts work as a whole,
then carrying it into native UI. The source is the reviewed local HTML account
study plus the explicit conversation decisions. References inform presentation;
they do not reopen these decisions.

## Locked

| Surface | Decision |
| --- | --- |
| Home | Accounts live in the feed. Show every non-archived account; no View all / Show less, cap or internal scrolling. The section pushes later content down. |
| Accounts heading | Text only. Add (+) and section options (…) on the right. |
| Tap | Open the account's balance and activity. |
| Hold | Open account actions: rename, add transaction, archive. Icons on the left. No move-to-space or delete action. |
| Section options | Reorder accounts and Archived accounts, with leading icons. No archived counter. |
| Reorder | Explicit mode entered through section options. Show drag handles in the Home section and Done. Holding a normal row continues to mean account actions. |
| Archive | Hide the row while preserving its data/history. Offer Undo; archived accounts can be restored. |
| Account detail | Native back navigation; one consistent (…) action entry. No separate pencil or duplicate management heading. Balance and activity lead; one obvious add-transaction action. |
| Add account | Cash, Checking, Savings, Investment, Credit card, Loan. Other assets expands Property, Vehicle and Other asset. Original approved vector icons. |
| Required fields | Type required. Name optional, falling back to type; balance optional and blank means unknown, not zero. |
| Amount | Currency code and picker inside the left edge, number right aligned. No repeated symbol/code or formatted readback. Plain native field background. |
| Typing | Latest reviewed HTML uses whole-number entry, optional decimal cents, live comma grouping, padding on blur. This supersedes the earlier cents-first experiment. Keep selection/caret; reject letters, excess precision and amounts above 9,999,999.99. Never silently round pasted amounts. |
| Input tone/motion | Empty 0.00 is gray; positive entry uses a legible teal. Grouping motion must not delay the actual entered value. Respect Reduce Motion. |
| Add action | Disabled while the type is missing or input needs correction. A contextual info lip slides above the action and collapses when valid. |
| Copy | Name; Loan; Other assets. Remove fictional-information footer, Private to you, and leave-blank helper. Optional labels remain. |
| Navigation | Home, Plan/target, assistant, Search, Profile. No visible icon labels. No Accounts tab. Exact approved Home icon; assistant mark remains provisional. Bell at upper right. |

## Still open or preserved elsewhere

- Home composition beyond Accounts, final branding, typography/spacing polish,
  assistant mark and navigation-bar motion remain open for review.
- Swipe actions are deferred. Native does not inherit the green web swipe control.
- Balance-check semantics and detailed reconciliation remain owned by the existing
  connected financial experience. Do not redesign them as part of this pass.
- Account-detail monthly summaries, richer editing metadata, transaction types,
  inspection/correction and advanced asset details retain their existing product
  contracts. Their absence from a visual canvas is not a product-scope deletion.
- The current entry/review preview stages sample rows only; it does not implement
  ledger effects, reconcile balances, persist data, or call the API.

## Reference exercise

Inspected inline Mobbin screens on September 30, 2026:

- [Wise balances](https://mobbin.com/flows/469559a0-00d1-468e-abf8-6400019d6f3d):
  clear account identity/balance, actions, then transaction history.
- [Reminders reordering](https://mobbin.com/flows/cd8cc37e-987f-48fe-ae62-bbc38931471e):
  explicit edit mode, row handles and a completion control. Search requested
  Things; returned reference was Reminders and is identified accurately here.

These are captured flows, not claims about the latest installed app version or
animation timings. Apple [sheets](https://developer.apple.com/design/human-interface-guidelines/sheets)
keep a scoped task close to its context; [context-menu guidance](https://developer.apple.com/design/human-interface-guidelines/context-menus)
keeps object-specific actions out of the main layout. The founder's leading-icon
sheet choice is preserved using native presentation rather than web dialogs.

Implementation/evidence: [Accounts evidence](../reports/evidence/cuadrao-native-design/accounts/README.md).
