# Document extraction verification checkpoint

Implementation head: `45a1f2eb8745a8cbd9c8ddd6a683748dfc3d8202`.
Starting integration: `5d403d7bf97d8154b89d88613bdb706c3a35fbb1`.
Current integration: `5edd5a82bd5affaffea4365168fcc8aea35b19fa`.
Its intervening PR #775 changes only native design, Swift previews/tests and
design evidence. There is no shared runtime owner, API/data contract, UI state
owner, migration, environment variable or affected test with this extraction
lane. Existing acceptance evidence is retained; the final PR audit records the
one-way reconciliation merge and exact-head CI.

## Verified offline

- 632 focused tests passed. Two database tests skipped because
  `ARGUS_DISPOSABLE_DATABASE_URL` is not configured locally.
- 272 required mocked eval tests passed. Repository-wide Ruff, lock validation,
  OpenAPI compatibility, fixture pair validation and modularity passed.
- The HTTP acceptance test uses actual PNG bytes and local image preparation,
  with only the provider response scripted. It uploads, creates canonical
  candidates, resolves the account, previews through MoneyService, confirms
  acceptance and verifies duplicate upload/acceptance creates one activity.
- PDF preparation reads and renders both pages of the actual synthetic PDF.
  Invalid/oversized images, invalid/encrypted/oversized PDFs, missing tools,
  incomplete model output, truncated responses and unknown fields are rejected.
- Recovery tests cover a saved extraction before failed candidate delivery,
  successful delivery before failed completion, concurrent duplicate uploads,
  expired workers, owner isolation and disconnect during extraction.
- Six fixture pairs include two official CORD receipts licensed CC BY 4.0,
  Spanish DOP and USD statements, a synthetic receipt and an unreadable image.
  Original public annotations, attribution, checksums and independent expected
  financial rows are committed under `tests/document_extraction_fixtures/`.

The local SciPy binary initially prevented eval collection. Reinstalling the
same locked version using its official macOS 12 ARM wheel restored both SciPy
and scipy.linalg imports; no application change was made for that failure.

## Independent review

A bounded Codex review checked ownership, durable checkpoints, disconnect races,
provider output, candidate-only delivery, retries and comments. It found one
P2 issue: macOS rejected an unconditional address-space limit before PDF tools
could run. The fix uses Linux address-space limits and process RSS monitoring,
with CPU, file and elapsed-time limits. The reviewer reran both failing tests
and the canonical vision-tier migration test. Its final delta review reported
no remaining P1/P2 findings. A subsequent Linux CI run found only a fixture rendering mismatch (9,954 other
backend tests passed). Synthetic PNGs now use embedded bitmap glyphs and
regeneration checks exact decoded pixels rather than compression bytes. Both
image/label pairs were visually rechecked and hashes refreshed. Independent
delta review was clean, with 30 focused tests passing. The full focused suite
again passed 632 tests. All delegated work is complete.

## Unverified and pending

The founder approved six documents, one attempt each, with a US$2 cap, using
the existing development key. The selected model is
`deepseek/deepseek-v4-flash-vision-exp`.

The six approved documents were each attempted once, with no retries.
The first three attempts failed at the provider boundary. The synthetic DOP
statement exposed an embedded 400 response: `Grammar error: Unimplemented keys:
["uniqueItems"]`. The model-output uncertainty field used a frozenset, which
Pydantic encoded with this unsupported keyword. Commit `e624cb9a` changes only
that model-facing field to an immutable tuple; canonical ImportCandidate
uncertainty still deduplicates into a frozenset. A regression failed before the
fix and passed after it. Independent review returned clean.

The remaining three approved samples ran on the fixed schema. The USD statement
and DOP receipt returned valid structured candidates, but strict scoring found
zero of the three expected transactions classified as transaction evidence.
The unreadable fixture was correctly rejected. No balances were classified as
transactions. These results fail live extraction acceptance; they are not a
successful extraction-quality claim. Actual candidate field snapshots were not
retained, so no unsupported explanation for the misclassification is asserted.

Post-fix elapsed times were 77,627 ms for the USD statement, 16,818 ms for the
DOP receipt and 3,387 ms for the unreadable image. Their measured total cost was
$0.00489199536. The first three provider rejections had no cost receipts, so
actual total cost remains unknown. All six conservative reservations remain
consumed, totaling $1.4030075136 within the $2 approval. No key limits changed.

The [complete attempt summary](live-benchmark-summary-2026-10-02.json) preserves
all six outcomes, per-attempt code heads, quality scores and usage. The
[initial stopped report](live-benchmark-2026-10-02.json) also retains the dated
public endpoint snapshot. No private document text or credentials are included.
Three failed samples were not repeated after the schema fix, honoring the
single-attempt scope. Further paid validation needs a new bounded approval.

The runner uses the existing development key and a run-local reservation.
Each actual POST reserves a full uncached context window plus the canonical
output limit, pins a verified endpoint and sets provider price ceilings.
Separate request and image fees are prohibited. A second attempt is blocked
before HTTP; unknown cost stops the run. No key or account limits are changed.

The benchmark's offline mode validates hashes and recorded pair review. The
fixture tests separately check original annotation/image pairs and PDF table
arithmetic. Expected labels never enter production extraction inputs.

The push CI disposable Supabase matrix passed, including the two new PostgreSQL
tests. Final-head CI is recorded on the PR. Poppler exists
locally and CI installs it explicitly; hosted Poppler availability is not proven.
Deployment requires applying the two migrations and provisioning PDF tools,
Pillow, a vision model and registered provider credentials. The feature defaults
off. No manual hosted migration, deployment or merge was performed. The repository's
automatic Supabase PR preview ran successfully.

Native design, existing demos and other connectors were not modified. There is
no Dominican-bank compatibility claim. This checkpoint is not a READY claim.

## Reproduce

```sh
poetry run pytest tests/ingestion tests/document_extraction_fixtures tests/test_openrouter_policy.py tests/test_openapi_compatibility.py tests/test_route_receipt_tiers_migration.py tests/test_document_extractions_postgres.py -q --no-cov
poetry run python -m scripts.documents.benchmark --output temp/document-offline-new.json
poetry run python scripts/check_modularity_budget.py
```

After explicit approval, set the configured model and existing local dev key
without committing them, then run once with a new output path:

```sh
poetry run python -m scripts.documents.benchmark --live --max-documents 6 --spend-cap-usd 2 --output temp/document-live-new.json
```

## Run-budget correction

The dedicated key-cap prerequisite was an unnecessary benchmark restriction.
The runner now uses the existing local `OPENROUTER_API_KEY`. Two bounded design
reviews selected a ContextVar guard at the actual HTTP POST over passing
benchmark arguments through domain APIs. One budget owns attempts and reserved
spend; ordinary runtime requests remain unchanged outside its scope.

A clean independent delta review passed 24 focused tests. Full focused checks
passed 639 tests after the schema regression was added. Public endpoint metadata supports a full-context reservation
of $0.2338345856 per request, or $1.4030075136 for six requests. Price ceilings
are enforced by [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection#max-price);
endpoint metadata and actual cost remain part of the live report.
