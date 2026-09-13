# Time to first token by turn type, issue #462

Ordinary chat has a substantial wait before answer text on the deployed product. Research adds another wait; an early background acknowledgement is not a grounded answer. The measurements below establish the baseline for [issue #462](https://github.com/lagarcess/argus/issues/462) and [board decision 3](../specs/argus-grounded-finance-roadmap.md#decisions). No latency optimization, model-facing text, tier, timeout, UI, or product configuration changed.

**Real run:** 2026-09-08, 21:01:20–21:35:39 UTC; 68 sequential HTTP turns on `https://api.arguschat.ai`, with real providers, Supabase/Postgres persistence and Render Workflow backtests. The deployed API/web commit was `ee9c3491fa6219502f1e94abc5d9e661a06839d9`. The isolated measurement worktree starts at the requested `00331188c9e42bb86b74042d0a74a8e24e423af3`; this report does not claim that revision was deployed. The calculator registry is absent, so actual compute-answer TTFT is **unmeasured**, not zero.

Existing receipts supplied provider-call durations and tier counts, but no first-token clock. The TTFT, delivered-card, stage and end-to-end completion distributions required this new client measurement.

All times are seconds. TTFT is arrival of the first non-whitespace SSE token at the HTTP client, **not browser paint**. Completion means `[DONE]` for synchronous turns and receipt of the terminal result artifact for jobs. These are empirical nearest-rank quantiles; at n=10, p95 is the maximum, not a stable population tail estimate.

| Observed turn type | n | TTFT p50 | TTFT p95 | Completion p50 | Completion p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary chat | 10 | 33.14 | 48.21 | 34.00 | 49.44 |
| Clarification of a backtest request | 2 | 37.61 | 53.20 | 38.84 | 57.11 |
| Confirmation card | 8 | none | none | 27.44 | 35.19 |
| Compute-intent prompt: LLM reply | 8 | 19.07 | 36.35 | 19.58 | 37.18 |
| Compute-intent prompt: clarification | 2 | 15.73 | 32.97 | 16.35 | 34.02 |
| Research fast | 10 | 15.96 | 23.64 | 16.21 | 23.86 |
| Research balanced | 10 | 25.95 | 43.10 | 26.18 | 43.58 |
| Research thorough: successful | 7 | 11.84 | 13.66 | 45.75 | 61.75 |
| Research thorough: degraded | 3 | 15.11 | 22.45 | 41.69 | 54.29 |
| Backtest run: acknowledgement | 8 | 2.55 | 3.87 | 16.27 | 60.99 |

The 8 confirmation cards emitted **no token events**. Their first delivered content was the card: p50 27.44s, p95 35.19s. Two intended DCA confirmations instead requested clarification; both are retained above and triggered no run. The executed cohort includes buy-and-hold and DCA with explicit recurring contributions.

Compute-intent rows are diagnostic probes of the existing conversational path, not calculator results. The working target remains **compute <1s, grounded <4s**, subject to founder review; neither is enforced. Every probe and research answer in this run arrived above its corresponding working threshold, but the absent compute capability still requires its own measurement when built.

## Grounded answer versus acknowledgement

| Successful thorough path | n | First text p50 / p95 | Grounded answer available p50 / p95 |
| --- | ---: | ---: | ---: |
| Cache hit | 1 | 11.11 / 11.11 | 11.11 / 11.11 |
| Cache miss | 6 | 11.84 / 13.66 | 45.75 / 61.75 |

The one-second polling delay is **in addition to HTTP time**. Recorded completion is an upper bound at this client; the full poll trace and server timestamps are retained. Degraded responses never count as successful grounded answers. Cache hits retain old provider usage fields, and thorough usage latency can describe a poll, so neither field substitutes for the new end-to-end clock.

## Where the chat wait occurs

The client observes the following stage intervals. The interpret node includes its downstream audits, repairs and, for research turns, retrieval/composition; it is broader than the main structured LLM call. The last column isolates that main call using existing receipts, summing retries within a turn before taking the distribution.

| Observed type | Request to first stage p50 | Interpret start to first outcome p50 | First outcome to first content p50 | Main structured call p50 / p95 |
| --- | ---: | ---: | ---: | ---: |
| Ordinary chat | 1.32 | 31.23 | 0.36 | 9.20 / 13.63 |
| Confirmation card | 1.26 | 25.33 | 0.97 | 11.08 / 16.57 |
| Compute-intent prompt: LLM reply | 1.33 | 17.36 | 0.19 | 8.53 / 11.59 |
| Research fast | 1.13 | 14.62 | 0.20 | 6.87 / 14.20 |
| Research balanced | 1.31 | 24.06 | 0.23 | 9.08 / 29.81 |

The per-schema preflight, audit, repair and composition distributions are in [summary.json](evidence/issue-462/summary.json). These conditional call durations do not add up to percentile totals. No counterfactual speedup is inferred.

## Which tiers serve turns

The historical read-only snapshot covers the 30 days before the preliminary probe. Of **228 requests with correlation IDs**, structured/tier 3 made a successful call in **225 (98.7%)**, chat in 46 (20.2%), and context in 3 (1.3%). This supports the founder's read for the observable cohort. The percentages overlap because a request can use several tiers. There were 1,593 receipt rows, including 351 without request IDs; all 286 utility rows lacked one, so utility's historical turn share is unknown, not zero.

For the measured cohort, these counts distinguish successful and positive-latency attempted API calls captured for each request; they exclude out-of-band title generation and Workflow result composition. Successful-call counts are also retained in the JSON. They must not be read as the whole product's traffic mix.

| Tier | Turns with a successful call | Turns with a positive-latency attempt | Receipt rows |
| --- | ---: | ---: | ---: |
| utility | 0 / 68 | 0 / 68 | 0 |
| chat | 12 / 68 | 12 / 68 | 13 |
| structured | 60 / 68 | 60 / 68 | 219 |
| context | 0 / 68 | 0 / 68 | 0 |

**Tester attribution:** the ordinary pre-answer wait is sufficient to explain the complaint and is the broadest shared wait in this cohort. Research adds a distinct delay. Without the tester's original turn/trace, these measurements cannot determine which wait that person hit on August 11.

## Evidence and limits

- [Raw observations](evidence/issue-462/observations.jsonl), [recomputed distributions](evidence/issue-462/summary.json), [fixed EN/ES cohort](evidence/issue-462/cohort.json), and [method/reproduction notes](evidence/issue-462/README.md).
- [Collection provenance and recorder audit](evidence/issue-462/collection-provenance.json), [deployment during the run](evidence/issue-462/deployment-during.json), [deployment after the run](evidence/issue-462/deployment-after.json), and [historical SQL](evidence/issue-462/history_queries.sql).
- Six preliminary observations remain separate because they exposed a missing confirmation projection in the recorder. All primary records were checked for missing final/DONE events, transport errors, duplicate samples and missing terminal artifacts after the recorder review. No affected primary sample was found.
- This is one fixed workload, one existing QA identity, one client/network and one run window. It mixes natural cache states and is not a load test, a controlled cold-start experiment, a browser-render benchmark, an eval scorecard, or evidence for the unimplemented calculator.
- Test conversations were [archived](evidence/issue-462/cleanup.json); no customer text, identifiers, raw answers, or credentials are published. See [verification](evidence/issue-462/verification.json) for the focused tests, clean measurement review, runtime no-touch check and integration provenance.
