# Retrieval parameters: live recordings (#404, #545)

Grounded-finance board, item "Retrieval parameters". The board's proof is a
recorded response showing typed rows under a strict schema, and one
domain-filtered call citing a local source. Both are here, plus the probes
that decided how the parameters are wired and what the provider actually does
with each one.

Every recording went through the repository's own client, prompt builder and
spec derivation (`probe_retrieval_parameters.py`), so each `request` is byte
for byte what production sends. Files hold the request body, HTTP status, raw
response, the parsed packet and the candidate SHA. No credentials, no user
data. Recordings vouch for runtime head `7ef0055b`; the later heads in the
table only added probes to the script.

Captured 2026-09-08 between 20:20 and 21:00 UTC, after the US close. Total
provider-reported spend for the fourteen files on disk: $1.40; earlier
overwritten runs bring the lane's spend to roughly $2.

## Recordings

| Probe | Head | Shape | Exchanges | Status | Typed | Rows kept | Rows dropped | Tool results | Public sources | Served model | Cost USD | Seconds |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- | ---: | --- | ---: | ---: |
| `fast_quote_typed` | `7ef0055b` | fast | 1 | 200 | yes | 1 | 0 | finance_results | 0 | openai/gpt-5.6-sol | 0.047 | 6.17 |
| `typed_rows_current_external` | `7ef0055b` | balanced | 1 | 200 | yes | 3 | 0 | fetch_url_results,finance_results,search_results | 41 | openai/gpt-5.6-sol | 0.182 | 29.99 |
| `domain_filtered_local_source` | `7ef0055b` | balanced | 1 | 200 | yes | 0 | 0 | search_results | 5 | openai/gpt-5.6-sol | 0.056 | 9.74 |
| `domain_filtered_rate_publishers` | `7ef0055b` | balanced | 1 | 200 | yes | 0 | 0 | search_results | 0 | openai/gpt-5.6-sol | 0.060 | 19.38 |
| `domain_filtered_rate_publishers_no_recency` | `b7174ef4` | balanced | 1 | 200 | yes | 0 | 0 | fetch_url_results,search_results | 29 | openai/gpt-5.6-sol | 0.151 | 32.73 |
| `market_pulse_vaguest` | `7ef0055b` | balanced | 1 | 200 | yes | 0 | 0 | search_results | 38 | openai/gpt-5.6-sol | 0.078 | 12.89 |
| `market_pulse_vaguest_rail` | `503db34d` | balanced | 2 | 200 | yes | 0 | 0 | fetch_url_results,search_results | 5 | openai/gpt-5.6-sol | 0.350 | 45.48 |
| `market_pulse_retry_finance_only` | `d7ef00fa` | balanced | 1 | 200 | yes | 0 | 0 | none | 0 | openai/gpt-5.6-sol | 0.024 | 2.28 |
| `retry_variant_prose` | `d87ef80e` | balanced | 1 | 200 | prose | 0 | 0 | none | 0 | openai/gpt-5.6-sol | 0.028 | 3.75 |
| `retry_variant_no_instructions` | `d87ef80e` | balanced | 1 | 200 | yes | 0 | 0 | none | 0 | openai/gpt-5.6-sol | 0.031 | 5.95 |
| `retry_variant_instructions_v2` | `d87ef80e` | balanced | 1 | 200 | yes | 0 | 0 | none | 0 | openai/gpt-5.6-sol | 0.031 | 3.77 |
| `tool_choice_required` | `7ef0055b` | balanced | 1 | 200 | yes | 0 | 0 | fetch_url_results,search_results | 36 | openai/gpt-5.6-sol | 0.247 | 40.23 |
| `models_fallback_forced` | `7ef0055b` | fast | 1 | 400 | - | 0 | 0 | none | 0 | - | 0.000 | 0.15 |
| `thorough_typed_background` | `7ef0055b` | thorough | 2 | 200 | yes | 10 | 0 | finance_results | 0 | anthropic/claude-opus-4-7 | 0.117 | 21.23 |

"Public sources" is the bounded pool the parser retains (up to 64); the
drawer shows at most five. "Rows dropped" counts rows whose citation matched
no page the same response retrieved.

## The two proofs

**Typed rows under a strict schema.** `typed_rows_current_external` asks "Why
is NVIDIA stock moving this week?" through the balanced shape. The answer
arrived as the schema: prose plus three rows (the Hugging Face acquisition
value cited to a Reuters page, the closing price and the daily change cited
to the provider's finance data). Every web citation carries the publisher's
date and every date falls inside the one-week recency window; the
fourteen-month-old article #545 documented cannot enter. `fast_quote_typed`
and `thorough_typed_background` show the same schema honored on the fast
shape and on the Anthropic model in background mode.

**A domain-filtered call citing a local source.** `domain_filtered_local_source`
asks, in Spanish with `user_location` DO, what Banco Popular pays on a one-year
peso certificate, with the web search restricted to the seeded list
(`popularenlinea.com`). The provider's own queries became `site:` searches,
every one of the five pages cited is on that domain, and the answer says the
rate could not be verified on an official public page. That is the honesty
line working: Banco Popular's site lists its certificates but publishes no
rate ("consult at branches").

## What each parameter does, measured

- **`response_format`, strict json_schema.** Honored by `openai/gpt-5.6-sol`
  and `anthropic/claude-opus-4-7`, inline and in background mode. The
  response echo still says `text.format: text`; the message text is the JSON.
  No first-use latency was observed on the fast shape (6 seconds).
- **`models`, the fallback chain.** Accepted. The chain passes over a model
  that fails or is unavailable; it does not pass over an unsupported model
  id. `models_fallback_forced` puts a nonexistent id first and the request
  fails validation in 0.15 seconds with `models[0]: model ... is not
  supported`. A typo in the chain would break every call, which is why the
  configuration test pins both models to the pricing table.
- **`instructions` and `language_preference`.** Sent on every call; the
  Spanish probe answered in Spanish.
- **`search_recency_filter`.** Derived from the question's section 7 data
  class. On the NVIDIA question it kept every citation inside the week. On
  regulator sites it is too tight: `domain_filtered_rate_publishers` restricts
  the search to `popularenlinea.com`, `sb.gob.do` and `bancentral.gov.do` and
  gets zero results for nine queries under the one-week window; the same
  list without the window (`_no_recency`) returns central-bank pages. Rate
  tables are updated monthly and published as Excel and PDF, so the future
  local rate calculation needs its own data class and HTML sources that
  render the rate. Neither probe changes the seeded list; they inform the
  founder's list.
- **`user_location` and `search_domain_filter`.** Both honored, see the
  second proof. The filter is a hard allowlist, so no rail shape opts in
  today; the first local calculation declares it.
- **`tool_choice`.** #404 asked for a documentation check and a live probe
  before anyone builds on it. It is undocumented, accepted, and ignored:
  `tool_choice_required` sends `required` and the response echoes `auto`.

## #404, the vaguest market pulse

The issue: "anything interesting moving today" could be answered from model
knowledge with stale figures presented as current. Under the typed contract
that answer is unrepresentable: a figure must be a row cited to a page this
response retrieved, and a row citing anything else is dropped and counted.

What the model does today, after the close, on the vaguest phrasing: it
retrieves (three web searches and fetched pages in every attempt) and writes
no figure. `market_pulse_vaguest_rail` drives the rail's own grounded path:
the first attempt came back typed with no row, the concrete retry fired once
(logged `reason=no_rows`), also retrieved, also wrote no row, and the turn
degraded honestly as `survey_synthesis_incomplete` with the sentence "I found
sources, but could not extract today's market movers from them." Five public
sources, no figure, no URL in the prose.

Movers are a structured finance dataset (operating rule 5), so the retry was
also tried with the finance tool alone. The model loads the finance skill and
declines to call it, in every request shape: the shipped one
(`market_pulse_retry_finance_only`), the pre-lane prose shape with no
instructions and no schema (`retry_variant_prose`), the schema without
instructions (`retry_variant_no_instructions`), and a retrieval-first
instruction wording (`retry_variant_instructions_v2`). Four for four,
"I could not retrieve current figures." The refusal is the provider's, not
the request's, and it is not something a parameter can force since
`tool_choice` is ignored. The retrieval instructions therefore stay as
shipped; the alternative wording measured no better.

Closure: the behaviour #404 names, asserting figures from memory, is gone by
construction and every recording shows it gone. Whether the vaguest phrasing
gets figures at all is now the provider's willingness to serve movers, and
the rail says so honestly when it will not.

## Two things the first recordings changed

- The Agents API emits a `fetch_url_results` item (`contents[]` with `url`,
  `title`, `snippet`) for every page the model opens. The reader table did
  not read it, so the first `tool_choice_required` recording dropped 21 rows
  that cited a fetched Yahoo movers page. Fetched pages now join the
  retrieval record and the typed sources; the re-recording drops none.
- A typed survey answer can retrieve and still carry no row. The existing
  concrete retry now fires on that as well as on no retrieval, once, and logs
  its reason.

## Also observed

Every `openai/gpt-5.6-sol` call logs `research_cost_unpriced` because the
invoice's input cost is outside the served-model rate table. #545 recorded the
same anomaly on both of its heads before this lane; answers are delivered and
the invoice is recorded as unpriced, per the pricing-delivery rule. Not
changed here.

## Heads after the recordings

Runtime head `7ef0055b` is what the requests and responses vouch for, and
every later commit was re-validated against them rather than re-recorded:
`tests/research/test_retrieval_contract_probe.py` rebuilds each recorded
request from the code at head and re-parses each recorded response with the
parser at head. The review-round fix `cd749fa0` changed only the composition
seam (a rejected row now withholds the whole answer, a figureless survey is
never accepted, a degraded sidecar carries no rows). The `turn` inside
`market_pulse_vaguest_rail.json` was composed at `503db34d`; the same two
exchanges compose to the same degraded outcome under the fix, which the
hermetic tests in `tests/research/test_retrieval_parameters.py` pin, so it
was not re-recorded.

## Re-recording

```bash
poetry run python docs/reports/evidence/545/probe_retrieval_parameters.py \
  --env-file .env --output-dir docs/reports/evidence/545/probes --probe all
```

Requires `PERPLEXITY_API_KEY` in the env file and a committed head. Every
probe is a paid call. `tests/research/test_retrieval_contract_probe.py` holds
the shipped instructions and schema against these files, so a change to
either has to travel with a new recording.
