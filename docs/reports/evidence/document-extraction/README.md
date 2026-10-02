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


## Qwen diagnostic preflight, October 2

The development environment resolves `document_extraction` to
`qwen/qwen3.7-plus` without a process model override. The founder authorized two
synthetic diagnostic calls, one USD statement and one DOP receipt, with no retries
and cumulative worst-case reservation below $2. **Neither call was dispatched.**

The [preflight report](qwen-preflight-2026-10-02.json) retains the dated public
[OpenRouter endpoint pricing](https://openrouter.ai/api/v1/models/qwen/qwen3.7-plus/endpoints).
Previous reservations remain $1.4030075136, leaving $0.5969924864. Even the lowest
tier's full-context reservation for two Qwen calls is $0.67072, bringing the
cumulative amount to $2.0737275136. That calculation understates the full bound:
Alibaba publishes higher rates above 256,000 prompt tokens and nonzero cache-write
pricing. The existing guard rejects this pricing shape as `no_bounded_endpoint`.
`max_tokens` bounds generated output, not input. No token estimate, fallback,
key-limit change or weaker guard was substituted to force dispatch.

The report separates scripted observations, canonical candidates, schema/candidate
validation and field-level scoring. These are **offline checks with a scripted
provider**, not Qwen extraction results. The actual outgoing synthetic JPEGs are
retained as [statement](qwen-preflight-statement-usd-p1.jpg) and
[receipt](qwen-preflight-receipt-dop-p1.jpg). Both are visually readable. The request
contains a 1600×1131 statement page and an 1100×700 receipt image; PDF text is
supplemental. The request retains strict schema output, no automatic fallback,
no reasoning retry, and the existing privacy restrictions.

Scripted transactions retain exact amounts, dates and directions after mapping.
Lowercase currency becomes the canonical uppercase code. The USD statement has
$40.25 outflow on September 7 and $100 inflow on September 8. Its $100 opening
and $159.75 closing balances remain balance candidates. The DOP receipt has one
DOP 250.50 outflow on September 10, not separate purchases for items or tender.

This inspection exposed a scorer false positive: the valid $100 income matched
the opening balance's amount. The scorer now subtracts exact expected transaction
matches before counting balance-valued surplus transactions. Two regression cases
failed before the one-line correction and pass afterward; duplicate surplus rows
remain detected. All 80 focused document tests and Ruff pass. This does not explain
or erase the earlier live zero-transaction results.

New paid cost is $0. No Qwen extraction latency or live quality result exists.
The original six-attempt results and their unknown cost portions remain unchanged.
Live acceptance is still incomplete. No new vendor, extraction pipeline, prompt,
model fallback, feature enablement, hosted configuration, merge or manual deployment
was introduced by this continuation.


## Qwen live diagnostic under the $6 ceiling

The founder approved a cumulative $6 reservation ceiling for the same two
synthetic diagnostics, one attempt each. The budget parser now reads all published
pricing tiers and reserves the highest prompt/cache input rate. The prompt routing
ceiling remains the highest published prompt price, separately from the larger
cache-write reservation. Malformed tiers and unknown nonzero charges still fail
closed. Thirty budget tests pass, including the third-attempt rejection. The
pricing and diagnostic instrumentation received independent review before dispatch.

The [live report](qwen-live-2026-10-02.json) identifies code head
`f8ad929008bc6f3d2ed833cd23bba488d142f6de`, the endpoint snapshot, exact request
image hash, schema hash, safe response diagnostics and consumed reservations.
The [runner](qwen-diagnostic-runner.py) matches the SHA-256 in that report.
Offline instrumentation checks exercised success, scoring failure and HTTP failure
before the paid run. They made no network requests.

Only the USD statement was dispatched. It failed with HTTP 404 after **815 ms**
including preparation. The captured error code is 404 and the error terms include
`privacy` and `no endpoints`. No model observations were returned, so schema
validation, candidate mapping and extraction accuracy could not be measured.
Empty observation arrays in the report represent absence of a model result, not
an extracted statement with zero transactions. The DOP receipt was not sent.
No retry, fallback, extra fixture or relaxed privacy request followed.

The existing request requires `zdr=true` and `data_collection=deny`. A subsequent
free read of the [public ZDR endpoint list](https://openrouter.ai/api/v1/endpoints/zdr)
returned no endpoint for `qwen/qwen3.7-plus`; the [safe readback](qwen-zdr-2026-10-02.json)
records the time and result. The selected model therefore has no listed route
compatible with the request's ZDR requirement at this checkpoint. This is a
provider/privacy compatibility blocker, not a missing key or demonstrated
candidate-normalization defect. Privacy settings remain unchanged.

| Measure | USD |
| --- | ---: |
| Approved cumulative ceiling | 6 |
| Previous six reservations | 1.4030075136 |
| Per-Qwen-call reservation, including highest cache-write rate | 1.24608 |
| Planned cumulative reservation for both calls | 3.8951675136 |
| Consumed cumulative reservation after one failed call | 2.6490875136 |
| New known actual cost subtotal | 0 |
| New actual cost | Unknown; no usage receipt |
| Cumulative known actual cost subtotal | 0.00489199536 |
| Cumulative actual cost | Unknown; four requests lack cost receipts |

The failed request retains its reservation. No charge is inferred from its HTTP
status, and an unknown invoice is not reported as zero cost. Remaining authorization
does not permit proceeding after this failure; another paid attempt needs approval.
No financial records were written. No PR merge, deployment, hosted setting change
or feature enablement was performed.
