# Reviewed document extraction

Starting integration base: `5d403d7bf97d8154b89d88613bdb706c3a35fbb1`.
Worker: `codex/document-extraction`. Target: `codex/private-alpha-next`.

## Outcome and boundaries

PDFs and receipt photos produce canonical `ImportCandidate` evidence in the
existing reconciliation queue. Only explicit acceptance through reconciliation
and `MoneyService` changes financial records. This implements the document entry
path in MVEE section 4 and extends `financial-ingestion-connectors.md`.

Native design, existing demos, chat interpretation, other connectors, production
configuration, merge and deployment are outside this lane. API upload is the
initial surface; any web control requires the user's scope answer.

## Contract

- Registered owner upload under the existing financial accounts and ingestion
  gates, plus a default-off document extraction flag.
- PDF, JPEG and PNG bytes are bounded and validated. Raw bytes and OCR text are
  transient and are never logged, persisted in candidates, or shared with a
  household. Upload consent explicitly covers sending content to OpenRouter.
- One owner-scoped document identity names a statement source connection.
  Concurrent attempts are leased. A validated extraction checkpoint is saved
  before candidate submission so retries replay identical source identities.
- Canonical candidates own extracted money facts. The checkpoint is a delivery
  outbox, not a second ledger. Disconnect removes its extracted content and
  existing reconciliation retention rules preserve accepted activity.
- Extraction distinguishes transaction rows, balance evidence and statement
  periods. Missing currency, date, amount or direction remains unresolved.
  Receipt items, taxes and totals must not become multiple purchases.
- Provider output is untrusted structured data, validated before any submission.
  Invalid, truncated, empty/unreadable or incomplete results cannot silently
  succeed. Bounded calls have no hidden retries.
- Existing OpenRouter credentials are reused. A dedicated vision model setting
  must be supplied explicitly; no silent model substitution. New configuration
  names and safe descriptions belong in `.env.example`.

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
claim Dominican-bank compatibility from synthetic or foreign fixtures. Escalate
if existing reconciliation cannot safely represent observed evidence; do not
bypass its confirmation boundary or change native design to complete this lane.
