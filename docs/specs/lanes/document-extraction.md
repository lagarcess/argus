# Reviewed document extraction

Starting integration base: `5d403d7bf97d8154b89d88613bdb706c3a35fbb1`.
Worker: `codex/document-extraction`. Target: `codex/private-alpha-next`.

## Outcome and boundaries

CAPTURE → SAVE → PREPARE → REVIEW → APPROVE. Founder clarification on October 2
supersedes the original extraction-before-save contract. Upload persists a private
source and durable draft even if preparation fails. The shared connection ID is
reused across entry surfaces. Only existing reconciliation and MoneyService
confirmation changes financial records.

Native design, demos, full Chat actions, payroll, new verticals and a complete
bill-splitting engine are outside this lane. No additional paid model calls,
merge, deployment, hosted configuration, privacy relaxation or feature enablement.
`ARGUS_VISION_MODEL` remains `openai/gpt-6-luna`.

## Contract and design decision

Extend the existing document checkpoint, rather than expanding every connector's
canonical candidate into a receipt/draft store. Keep one document owner and one
financial confirmation owner. See the [API contract](../../API_CONTRACT.md#document-capture-preparation-and-review).

- Retain bounded supported source files in the existing server-only checkpoint
  until explicit disconnect/deletion. Keep rendered/OCR intermediates transient.
- Persist source and preparation intent before asynchronous dispatch. Use the
  existing connection lease, fence completion, and mark interrupted provider work
  for attention without automatic retries. Re-deliver a saved batch without AI.
- Retain typed observations and receipt details; project compatible candidates
  individually and retain explicit issues for the others. Never silently drop,
  relabel or invent evidence to satisfy the canonical import contract.
- Receipt details include merchant/date/currency, items, quantities/prices,
  category suggestions, subtotal, tax/service, tip and total. Split/destination
  proposals remain separate from extracted evidence and confirmed financial data.
- Reuse the captured Luna response offline. Its unknown balance scope remains
  unknown; fixture knowledge must not be used to pretend the model identified it.
- Scope options for future preparation must distinguish opening, closing,
  available and running balances. Confirmation remains strict and owner-scoped.

## Verification and delivery

1. Validate licensed public receipt image/label pairs and separate synthetic
   Spanish DOP/USD fixtures. Keep labels out of extraction inputs.
2. Prove upload, candidate review, confirmed acceptance, retry and recovery over
   the existing API and MoneyService. Cover owner/guest isolation, disconnect,
   duplicate uploads, multipage tables, amount/currency/direction and balances.
3. Prepare a serial benchmark reporting row omissions/additions, field accuracy,
   latency, usage and cost. Obtain explicit sample-size and spending-cap approval
   before any paid request. Missing configuration is not a code defect.
4. Independently review the diff, reconcile current integration one way, run
   focused checks, mocked evals, modularity against the merged tree and CI.
   Commit durable evidence and deliver a reviewed PR. Do not merge or deploy.

## Stop conditions

Do not run paid requests without approval or a configured vision model. Do not
claim Dominican-bank compatibility from synthetic or foreign fixtures. Retain observations that cannot project into reconciliation on the same draft;
do not bypass confirmation or change native design to complete this lane.
