# The "why is it moving" gap: grounded answers that persist no typed sources

Five research turns, two heads, one process each, memory persistence, mock
auth, real interpreter and providers, `ARGUS_RESEARCH_RAIL_ENABLED=true`. Each
row links the compact transcript (role, first 300 characters, URLs found in
the prose, metadata keys, and the `research` sidecar when present). Route
receipt tasks are read from the backend log for that turn.

| Head | Question | Path the log shows | `research` sidecar | Sources typed | URLs in prose | Transcript |
| :--- | :--- | :--- | :--- | ---: | ---: | :--- |
| `5d408acf` | What has been going on with NVDA lately and why is the stock moving? | interpretation, then `knowledge_voicing` on the chat tier; no provider search task logged by the rail | absent | 0 | 3 | [`5d408acf-nvda-moving.json`](./rail-gap/5d408acf-nvda-moving.json) |
| `5d408acf` | What did Apple say in its most recent quarterly earnings report, and how did AAPL react this week? | interpretation, then the rail: two `finance_search` calls, pricing evidence | present, `balanced_lookup` | 5 | 0 | [`5d408acf-aapl-earnings.json`](./rail-gap/5d408acf-aapl-earnings.json) |
| `5761dd41` | What has been going on with NVDA lately and why is the stock moving? | same as above: `knowledge_voicing`, no rail search | absent | 0 | 3 | [`5761dd41-nvda-moving.json`](./rail-gap/5761dd41-nvda-moving.json) |
| `5761dd41` | Why is Apple stock moving this week? | same: `knowledge_voicing`, no rail search | absent | 0 | 3 | [`5761dd41-aapl-moving.json`](./rail-gap/5761dd41-aapl-moving.json) |
| `5761dd41` | What did Apple say in its most recent quarterly earnings report, and how did AAPL react this week? | the rail: two `finance_search` calls, pricing evidence | present, `balanced_lookup` | 5 | 0 | [`5761dd41-aapl-earnings.json`](./rail-gap/5761dd41-aapl-earnings.json) |

`5761dd41` includes #544, which changed `domain/research/admission.py`,
`search/selection.py`, `search/perplexity_direct.py`, `search/contracts.py`
and `search/openrouter_web_search.py`. The "why is it moving" shape still
falls through after it, so the gap is not something #544 fixed or caused.

## Where the fall-through happens

With the rail on, `knowledge_answer.knowledge_answer_stage_result` hands every
knowledge-shaped turn to `research_answer.research_answer_stage_result`. For
these questions that function does not run the rail's grounded path; it calls
back into `knowledge_answer._external_facts_answer`, which asks the search
provider for a packet, hands the snippets and URLs to the `knowledge_voicing`
task, and appends the packet's URLs to the prose when the model did not
(`knowledge_answer.py`, the `if "http" not in voiced` branch). Nothing typed
is persisted: no `sources`, no `retrieved_at`, no `anchor_symbols`, no
`degraded`. The transcript carries the URLs only as text.

## Why it matters beyond sharing

- The answer's sources are unverifiable by anything that reads typed
  metadata. The sources panel, the cost ledger's per-turn class, the
  follow-up seam and any future reader all see a plain prose turn.
- Under the sharing spec's eligibility rule (typed sources or nothing), the
  most common research question shape is unshareable, while a rarer
  earnings-report phrasing is.
- The pricing anomaly on the earnings turns (`research_cost_unpriced`,
  input cost outside the served-model rate table) is logged at ERROR on both
  heads and is a separate observation for the rail lane.

## Caveats

- One turn per phrasing per head, plus one extra phrasing on the second
  head. The interpreter is non-deterministic, so this shows the shape
  reproduces, not a rate.
- Market data was the synthetic fixture, which is why every question names
  AAPL or NVDA. The search provider and the interpreter were live.
- A first attempt at the earnings control on `5761dd41` was aborted by the
  driver closing the page mid-turn; the two provider calls had already run.
  The row above is the clean re-run.
