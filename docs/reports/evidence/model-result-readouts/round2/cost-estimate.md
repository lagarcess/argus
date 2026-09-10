# Second-round cost estimate

**Approval pending. No paid calls have run.** Final clean-checkout preflight
must confirm the request bound below before execution.

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

Free local sizing found an 82,317-byte largest complete request and an
86,832-byte maximum after an 8,192-byte allowance for the paired accepted
Quick take. That allowance is request headroom, not a new prose limit. Final
clean-tree sizing will be retained separately and must fit the same 90,000-byte
bound; stored evidence is not truncated to fit it.

Both arms use the same corrected source. Only the two task-tier mapping values
in `src/argus/llm/openrouter_tasks.py` differ. No market-data request, backtest,
browser turn, judge call, interpreter measurement or fingerprint regeneration
is included. No logical task may be rerun to replace an unfavorable result.
