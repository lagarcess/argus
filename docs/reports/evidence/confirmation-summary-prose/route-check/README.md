# Live route check

The figures for this run come from `route-check-report.md` and
`route-check-report.json`, which `summarize_route_check.py` builds from the
committed files in this directory.

## What ran

- `route_check_api.py` served the branch at the head recorded in `server.json`
  through the real chat route, with memory persistence, mock auth, OpenRouter
  models, and the `live_provider` market-data and asset modes. Personalization
  memory and semantic recall were set off.
- `route_check_driver.py` drove one conversation in `en` and one in `es-419`
  through `POST /api/v1/chat/stream`, with the cap recorded in `summary.json`.
  Each conversation sent a request to test buying and holding Apple with
  $10000, a message changing the amount to $5000, the card's Run action, and a
  question comparing the result with SPY. The messages are in the driver's
  `SCRIPTS`.
- The Spanish result question was asked once more in the same conversation,
  sent by hand after the driver finished, under the retry rule the driver now
  encodes.

## Files

- `server.json`: source head, whether `src` or `web` had working tree changes,
  port, override names, and a fixed `env_file` label.
- `model_requests.jsonl`: host, path, body, and status or exception name of
  each captured model request.
- `receipts.jsonl`: OpenRouter route receipts.
- `thread_history.jsonl`: reader, conversation and items of each captured
  thread history load.
- `naming_input.jsonl`, `naming_output.jsonl`: the contexts and names artifact
  naming built.
- `steps.jsonl`: one row per step.
- `summary.json`: the driver's summary.
- `route-check-report.md`, `route-check-report.json`: the report.

The server writes `research_costs.jsonl` only when research cost validation
runs; this capture has no such file.

## Known gaps

- A request body is recorded only for httpx requests to openrouter.ai or
  perplexity.ai whose send returns or raises an ordinary exception. A request
  cancelled by an asyncio timeout has no row. Responses and requests to other
  hosts are not recorded.
- The report shows only each captured request's non-system messages, and its
  markdown cuts each message at 600 characters; system messages are in
  `model_requests.jsonl`.
- A receipt is recorded when it is appended to OpenRouter's route receipt list.
  An unpriced receipt can be a skipped invocation that sent no request.
- The report assigns records to a step by write time, from the step's request
  until the next step starts. Only history loads are matched to a conversation.
- `steps.jsonl` was assembled after the run from the driver's local output and
  the hand-sent retry, and conversation ids were added later. The driver rows
  have no spend before the step; the retry row has no card facts or title, and
  its `reason` is a hand-typed note the report does not use. `summary.json` was
  written before the retry. The driver was revised after the run to write
  `steps.jsonl` and ask the retry itself.
- The driver's cap check is an estimate made before each step; a step can
  spend more than its reserve.
- Provider keys were loaded in-process from the env file named by
  `ROUTE_CHECK_ENV_FILE`, where values already set win, and Argus loads a
  repository-root `.env` at import the same way.
- The checks compare recorded card facts, look for a run in the final payload,
  and look for words in the reply. They do not judge whether an answer is right.
- Two conversations, one path each, on memory persistence. The steps include no
  clarification, recurring plan, discovery, retest or in-place edit.

## Reproduce

Rebuild the report from the committed files alone:

```bash
ROUTE_CHECK_OUT=docs/reports/evidence/confirmation-summary-prose/route-check python docs/reports/evidence/confirmation-summary-prose/route-check/summarize_route_check.py
```

Run a new check from the repository root, with `ROUTE_CHECK_ENV_FILE` naming an
env file that holds the provider keys:

```bash
ROUTE_CHECK_OUT=temp/route_check/branch ROUTE_CHECK_ENV_FILE=<env file> python docs/reports/evidence/confirmation-summary-prose/route-check/route_check_api.py
```

```bash
ROUTE_CHECK_OUT=temp/route_check/branch ROUTE_CHECK_CAP_USD=0.50 python docs/reports/evidence/confirmation-summary-prose/route-check/route_check_driver.py
```

```bash
ROUTE_CHECK_OUT=temp/route_check/branch python docs/reports/evidence/confirmation-summary-prose/route-check/summarize_route_check.py
```
