# Next assignment: statement-import contract

This file is a bounded assignment for the next agent. It follows from the [feasibility report](README.md). It needs no credential, no bank contact, no provider account, and no paid call, so it can start now.

## Goal

Write the technical contract that lets a person import a bank statement or transaction file into Argus as reviewable proposals and confirmed records. The contract must also let a future bank connection replace the retrieval method without replacing records.

The contract serves MVEE sections 4.4, 4.5, 4.7, 5, and 12. The documentation authority lists the financial-record schema, reconciliation, money arithmetic, retention, and permissions as undecided. This assignment proposes those contracts for founder approval. It does not implement them.

## Start from

- Freshly fetched `origin/codex/private-alpha-next`. Record its SHA as the lane base.
- `AGENTS.md`, `docs/DOCUMENTATION_AUTHORITY.md`, the MVEE, `docs/ARCHITECTURE.md`, `docs/API_CONTRACT.md`, `docs/DATA_MODEL.md`, and `.agent/designs/argus/DESIGN.md`.
- This lane's [integration map](integration-map.md), [connector lifecycle experiment](connector-lifecycle-experiment.md), and [legal and regulatory matrix](legal-regulatory-matrix.md).
- `tests/synthetic_ingestion/` and its evaluation in `docs/reports/synthetic-ingestion-evaluation.md`.
- `docs/reports/payment-ledger-reuse-assessment.md` for money rules.

## Deliverable

One documentation-only pull request to `codex/private-alpha-next` that adds a contract under `docs/specs/`. The contract covers these items.

1. **Records.** Accounts, transactions, balance snapshots, balance checks, import batches, and source documents. For each one, give its fields, identity, owner, and intended row-level security.
2. **Money.** An amount type in integer minor units or `Decimal`, per-currency fraction digits for DOP and USD, parsing of `RD$`, `US$`, and `1.234,56`, and the rule that an unqualified amount is never read as dollars or pesos.
3. **Observation identity.** Strong identity from an institution id. Derived identity with an occurrence index when no id exists. Overlapping files, pending holds, reversals, source revisions, and rows a source stops reporting.
4. **Review.** Batch confirmation with exceptions first, the list of blocking and informational issues, matching against manual and chat records, and transfer pairing with and without a bank reference.
5. **Provenance and dates.** Source kinds for entered, extracted, connected, and calculated facts. Activity date, statement date, and capture or refresh time.
6. **Field ownership.** Which fields a source may revise and which fields become owner-owned after an edit.
7. **Source documents.** Storage location, visibility, retention period, and purge on deletion.
8. **Privacy.** Record content stays out of logs, analytics, the shared research cache, sharing snapshots, and model prompts until a separate decision says otherwise. Name the test or lint that enforces each rule.
9. **Connections, reserved.** The connection states, consent record, vault handle, and refresh health from the experiment, marked as reserved for a later lane and not built now.
10. **Decision 8.** A proposed reconciliation of archived decision 8 with MVEE section 4, marked for founder approval. Do not settle it silently.
11. **Acceptance tests.** One behavior test per case in the experiment's 25 checks, stated so an implementation lane can write them first.

## Acceptance criteria

- Every one of the experiment's 22 cases maps to a contract rule and an acceptance test.
- Every item in the integration map's unresolved contracts has a proposed rule or a named open question for the founder.
- The contract changes no runtime code, schema, migration, prompt, model-facing text, analytics event, or dependency.
- The contract proposes, and does not apply, any change to `docs/API_CONTRACT.md` or `docs/DATA_MODEL.md`.
- `git diff --check`, `scripts/check_docs_links.py`, and the docs-reading tests that scan `docs/` pass on the exact head.
- The pull request lists the lane base and the current integration SHA at the time of the ready claim.

## Stop conditions

Stop and report instead of choosing when any of these happens.

- A rule needs a provider choice for OCR, storage, or email.
- A rule needs the founder's decision on decision 8, automatic acceptance, pending holds, guest imports, or deletion scope.
- A rule conflicts with the MVEE or with an assigned Wave 1 package.
- A rule needs real bank documents to settle a field. Name the field and continue with the rest.
- A second review finding arrives on the same mechanism after one fix.

## Work that needs someone else first

These tracks can run beside the contract. None of them is part of the assignment above.

| Track | Who | First step | What it establishes |
| --- | --- | --- | --- |
| Consented statements | Founder | Export one month from each format the chosen bank offers on the founder's own account, following the consent and retention checklist in `tests/synthetic_ingestion/README.md` | Which fields, pages, currencies, and history depth real files carry |
| Bridge developer test | Founder, on Bridge's free Developer plan | Read the institution list in the sandbox, then link the founder's own accounts at two or three banks for two to four weeks | Named coverage, MFA steps, refresh cadence, reconnection frequency, security alerts, and revocation behavior |
| Dominican counsel | Founder engages counsel | Send the questions in the legal and regulatory matrix | Whether consented credential use, in-session extraction, and cross-border storage are permissible for the specific design |
| Bank conversations | Founder | Use the partnership evidence proposal, without sharing any person's data | Whether a bank would sanction a narrower channel |
| Product decisions | Founder | Decide decision 8, pending holds, automatic acceptance, deletion scope, and stored secrets | The inputs the contract marks as open |

An agent may analyze the output of the consented-statements track only after the founder confirms consent and retention in writing. Only sanitized field names, formats, and counts may enter the repository.
