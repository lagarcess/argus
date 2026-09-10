# Second-round cost estimate

**Approval pending. No paid calls have run.** The committed-input
[preflight](preflight.json) confirms the request bound below.

| Arm | Logical tasks | Conservative maximum USD |
| --- | ---: | ---: |
| Current chat/context | 48 | 5.094912 |
| Both readouts structured | 48 | 44.688000 |
| Total | 96 | **49.782912** |

Proposed founder cap: **$50 for this round only**. The earlier $5 approval
does not authorize it. This is a worst-case reservation, not an expected bill.

The [price snapshot](prices.json) records independently highest displayed
input/output provider rates without cache discounts. The structured setting
resolves to Grok 4.3 with Haiku 4.5 fallback; current task mappings and provider
configuration are recorded by the final preflight. The bound includes Grok
Priority and Haiku regional pricing rather than assuming their cheapest route.

The reservation covers 90,000 input bytes per HTTP request, conservatively
counting each byte as a token, 700 output tokens for Quick take and 2,400 for
Breakdown, and four HTTP attempts for each logical task. Requests exceeding
that measured ceiling stop before dispatch. The full 90,000-byte reservation
is used even when the actual request is smaller. Missing provider costs retain
their complete reservation and are never called free.

Final clean-tree sizing found an 82,540-byte largest complete request and an
87,049-byte maximum after an 8,192-byte allowance for the paired accepted
Quick take. That allowance is request headroom, not a new prose limit. Both
fit the 90,000-byte bound; stored evidence is not truncated to fit it.

Current source: `cc0b32e19412a1bb483b8a6a45e982418b9dae34`.
Structured source: `955dfa86b40b176e6fbb9d1a5857d4dd35fe57ef`.
Both checkouts were clean. All 4,693 other tracked tree entries were identical.
The preflight covered all 48 scheduled visits / 96 frame tasks with zero HTTP
attempts. Its technical prerequisites being satisfied is not founder approval;
`approved_usd` remains zero.

Both arms use the same corrected source. Only the two task-tier mapping values
in `src/argus/llm/openrouter_tasks.py` differ. No market-data request, backtest,
browser turn, judge call, interpreter measurement or fingerprint regeneration
is included. No logical task may be rerun to replace an unfavorable result.
