# Preserve the money question during recovery

Founder-locked 2026-09-14, following acceptance PR #631 and the narrowed lane request.

## 1. Why

PRODUCT.md requires Argus to answer money questions by computing or citing and
never name a capability the user did not ask for. The grounded-finance roadmap
keeps the question's primitive; the decision memo's failure and recovery trust
section requires useful recovery in the user's language.

## 2. Locked decisions

1. Failed interpreter candidates cannot invent strategy ownership. Focused
   strategy repair requires evidence that this turn requests a test.
2. A pending reply does not own a new turn before its interpretation: knowledge
   and arithmetic questions can leave a pending test alone and be answered.
3. Research uses only the remaining turn budget, with time preserved for the
   existing answer-without-lookup path when retrieval cannot finish.
4. Interpreter recovery names the failed understanding/answer operation without
   inventing a test, asset, or period. English and Spanish copy uses no em dashes.

## 3. Reserved / parked scope

- History-only research admission is explicitly excluded by the founder.
- No model-facing text or schema descriptions, render.yaml, paid runs, hosted
  state, migrations, deployment, or merge changes.
- If a rule needs model-facing text, hold that rule, report the exact strings,
  and deliver the other rules.

## 4. Contract gates

- Update docs/ARCHITECTURE.md for the changed recovery and budget ownership.
- Existing recovery codes and transport remain compatible; no new persistence
  or public request schema is intended. Update API_CONTRACT.md if needed.
- Preserve locale catalog parity and the shared backend recovery fallback.

## 5. Execution contract

- One worker PR from codex/private-alpha-next, targeting that same branch.
- Original branch base: 0893c27e878f8b55c39afb467cba15ed0ed3cfee. Before any
  implementation it fast-forwarded to current integration 6ec36797 (record the
  full SHA in final evidence). Red reproductions run on that integration tree.
- Scripted failures for the Q4 interpreter outage, Q8 pending/arithmetic path,
  Q1 bilingual recovery, and Q2 slow-provider deadline path. Stubs only.
- Run the full backend and frontend deterministic suites, mocked eval harness,
  applicable lint/type checks, merged-tree modularity check, and GitHub CI.
- Codex review at the final head must be clean, with no unresolved threads.
  Report original/current integration, reconciliation, overlap and evidence.
- Stop at the posted PR. The founder owns merge and deployment.

## 6. Stop conditions

- Hold any rule requiring model-facing text and report exact strings.
- Stop the lane if Codex raises a second finding on the same mechanism. Do not
  fix it again or request unchanged-head reviews.
- Report unavailable checks honestly; do not replace paid gates with claims
  from scripted stubs.

## Sources

- docs/PRODUCT.md
- docs/specs/argus-grounded-finance-roadmap.md
- docs/specs/private-alpha-next-decision-memo.md, Failure and recovery trust
- docs/reports/evidence/2026-09-14-acceptance/findings.md
- Founder request in this task, including no paid runs and no merge
