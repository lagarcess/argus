# Argus around the finance workspace

## Decision

Use adapted Argus presentation and a local conversation runtime over the existing
finance owners. The model selects typed capabilities. Account balances, plans,
imports, calculations and receipts come from their existing implementations.
The production application bootstrap is not imported.

Two independent sketches agreed on the frontend, semantic boundary and artifact
ownership. They differed on transaction composition. Candidate A proposed
extracting connection-taking functions from every domain. Candidate B proposed
an explicit transaction-bound store that existing synchronous writers can use.
The independent judge preferred A because an unrestricted compatibility adapter
could silently escape the outer transaction.

The captain selected B's bounded unit of work, with A's explicit dependency and
currency provenance. This is an explicit object passed to audited synchronous
handlers, never a monkey patch or a global replacement for Store. Registration
requires evidence that it cannot commit, open another connection, run scripts,
yield, cross threads or survive closure. A caught inner failure poisons the
whole transaction. If a writer cannot meet this contract, extract its
connection-taking function before registration. The judge's risk is a required
verification surface, not a waived finding.

## Interfaces

The frontend uses an Argus composer and transcript. Finance pages retain their
existing endpoints. Both surfaces reach the same finance writer.

```text
Text + explicit record references
  -> one structured semantic read
  -> typed read, calculation, draft, clarification or unavailable result
  -> canonical facts or persisted proposal
  -> explicit confirmation
  -> domain write + receipt + transcript in one transaction
```

The semantic catalog derives from the command input models and copied Argus
calculation declarations. No keyword, regular expression or language table
decides intent. Offline examples submit typed metadata and identify themselves
as examples. Free text without configured inference stays visibly unavailable.

The neutral local graph carries record and proposal references. It does not
store independent copies of balances or an executable strategy disguised as a
budget. A confirmed proposal identifies its normalized input, creator, household,
generation, revision, expiry and owned dependencies. A retry returns its receipt.

Public streams use data-only events. Final results are persisted before final
delivery. Reload reads canonical messages and artifacts. Existing assistant
receipts remain accessible as older conversations.

## Reuse boundaries

- Copy/adapt Argus's composer model, selection/paste behavior, transcript and
  action patterns, sidebar, Omnisearch and responsive interaction rules. Keep
  provenance for the copied sources. Supply local transport and identity.
- Copy the pure tool contracts, declarations and finance calculators. Preserve
  unknown/input semantics and actual algorithms. Keep financial calculations
  separate from exact monetary ledger writes.
- Keep Decimal and currency minor units in the local money owner. Account-bound
  amounts derive currency from the owned account. Accountless amounts require
  explicit currency or a visibly sourced preference. Empty guests have unknown
  currency until they establish it.
- Extend ledger import preview and commit. CSV and TSV parse as data under
  strict size, row, column and cell bounds. Explicit column/date/decimal mapping
  produces a frozen review. Source IDs and user-reviewed possible duplicates
  prevent silent loss or duplicate imports.
- Keep guest identity within the current local Identity owner. A guest receives
  an isolated household and fixed 24-hour lifetime. Claim preserves local
  artifacts. No hosted identity or email claim is implied.

## Jev

Jev's Decisions API is a classification interface, separate from chat
completions. It cannot replace arbitrary amount/date extraction. This lane
reduces avoidable interpretation work through explicit metadata and one
structured model read. Jev remains a separately measurable candidate until it
can eliminate a call while preserving bilingual, artifact-aware behavior.

## Required evidence

Confirm replay, injected partial-write failure, nested failure, cancellation,
role change, reset, expiry, cross-household record access and currency mismatch.
Each registered command must be synchronous and reach one existing writer.
Every calculation declaration must retain its typed validation.

Browser acceptance includes guest entry, money home, conversation, proposal,
receipt, recall, import, settings and navigation at the plan's five widths in
both languages. Visual inspection is separate from mechanical overflow tests.
