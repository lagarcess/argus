# Perplexity billing evidence

`perplexity_netflix_2026-09-03.json` is one real, completed Agent API response,
captured on 2026-09-03 UTC with the repository's balanced configuration and
a public Netflix earnings question. It contains no credentials or user data.
Request text, capture time, response id, model, usage, costs and output are
retained.

## What the provider bills

The published page, https://docs.perplexity.ai/docs/agent-api/models (rechecked
2026-09-09), still lists `openai/gpt-5.6-sol` at $5 input, $30 output and $0.50
cache reads per million tokens below 272k input tokens, and $10, $45 and $1
above. The 2026-08-07 recording `docs/reports/evidence/377/probes/equity_steps2.json`
was billed at exactly that: 81 uncached input tokens for $0.00041, 191 output
tokens for $0.00573, cache creation at $6.25 and cache reads at $0.50.

Every invoice since disagrees with the page and agrees with itself. This
fixture's $0.08591 bills 708 output tokens at $0.01416, which is $20 per
million, and the fourteen recordings captured on 2026-09-09 under
`docs/reports/evidence/545/probes` bill $4 input, $20 output, $5 cache creation
and $0.40 cache read on every sol response (the fast quote: 81 uncached tokens
for $0.00032, where the page's rate expects $0.00041). `anthropic/claude-opus-4-7`
bills its published $5, $25, $6.25 and $0.50.

The rate table in `argus.domain.research.pricing` therefore follows the bill,
not the page: a table that reads the page rejects every real invoice as
`rate_mismatch`, and rejected spend reaches no ledger. The long-context tier
has never been observed and keeps the published values. Tool rates remain
$0.005 finance search, $0.0025 web search, $0.0005 fetch URL, confirmed by the
same recordings.

## How the tests use the recordings

The shared test factory reads its complete invoice from
`perplexity_fast_quote_2026-09-09.json`, a frozen copy of the 2026-09-09 fast
quote recording (`docs/reports/evidence/545/probes/fast_quote_typed.json` as
captured at `ca517e45`); a copy, so re-recording that probe cannot move the
invoice every canned document bills at. It never computes prices from either
production rate table. Counter overrides in
synthetic tests deliberately leave the invoice unchanged unless a test
explicitly supplies synthetic costs; pricing arithmetic edge cases label those
costs explicitly and are not live recordings.

Delivery tests reconcile the 2026-09-09 sol and opus recordings against the
current table, so a rate change without matching recorded evidence fails. The
2026-08-07 recording, billed at the earlier schedule, is pinned as unpriced
spend: an invoice at a schedule the table does not carry is recorded for a
person to reconcile, never silently accepted. Tests of the unpriced path
perturb the table on purpose rather than relying on a disagreement the
provider no longer produces.
