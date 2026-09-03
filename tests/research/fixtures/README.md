# Perplexity billing evidence

`perplexity_netflix_2026-09-03.json` is one real, completed Agent API response,
captured on 2026-09-03 UTC with the repository's balanced configuration and
a public Netflix earnings question. It contains no credentials or user data.
Request text, capture time, response id, model, usage, costs and output are
retained. Its $0.08591 invoice fails the old validator at output_cost:
$0.01416 reported versus $0.02124 expected for 708 tokens.

The published rate table was rechecked on 2026-09-03 against:

- https://docs.perplexity.ai/docs/agent-api/models
- https://docs.perplexity.ai/docs/getting-started/pricing

Published Sol input/output/cache-read rates remain $5/$30/$0.50 per million
below 272k input tokens and $10/$45/$1 above; Opus 4.7 remains $5/$25/$0.50.
Tool rates remain $0.005 finance search, $0.0025 web search, $0.0005 fetch URL.
The historical cache-creation rate remains independently covered by the
2026-08-07 recording below. The current page does not publish that component.

The fresh bill disagrees with the published model rates in several components.
One aggregate invoice cannot establish a replacement rate schedule, so this fix
does not invent one or widen tolerance to call it reconciled. It returns the
answer and records the invoice as unpriced. Updating rates later must have
independent evidence; it cannot restore an availability gate.

The shared test factory reads the complete invoice from the existing real
recording `docs/reports/evidence/377/probes/equity_steps2.json`, captured on
2026-08-07. It no longer imports or computes prices from either production
rate table. Counter overrides in synthetic tests deliberately leave the invoice
unchanged unless a test explicitly supplies synthetic costs. Pricing arithmetic
edge cases label those costs explicitly; they are not live recordings.

Delivery tests cover the fresh invoice unchanged and perturb the table against
the historical recording. A separate reconciliation assertion on that historical
recording fails if the table drifts, even though delivery keeps succeeding.
