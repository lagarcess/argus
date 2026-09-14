# Live route check

The full live measurement was skipped for this change: it builds each case's
history itself, so it cannot see how card turns reach the model. This capped
check drives real turns through the chat route instead.

## What ran

- Head `4e89d289` with a clean tree (`server.json`). `route_check_api.py`
  served the branch with memory persistence and mock auth, real OpenRouter
  models, and live Alpaca market data and asset catalog. Provider keys came
  from the canonical integration env file, loaded in-process and not committed.
  Personalization memory and semantic recall were off, so no memory lookups ran.
- `route_check_driver.py` drove two conversations through
  `POST /api/v1/chat/stream`, one in English and one in Spanish, four steps
  each: create a card (Apple buy and hold, January 2023 to December 2024,
  $10000), change an input ("make it $5000"), run it with the card's own Run
  action, and ask about the result ("How did that do compared to SPY?",
  "¿Cómo le fue frente a SPY?"). Artifact naming ran after every turn.
- Retry rule: a result question that returns a retryable typed recovery is
  asked once more, recorded as its own step, and never replaces the first
  result. During this capture the Spanish retry was sent by hand under that
  rule; the driver now encodes it.
- Captured:
  - `model_requests.jsonl`: every request body sent to OpenRouter, never headers.
  - `receipts.jsonl`: every cost receipt.
  - `thread_history.jsonl`: the history the chat route and artifact naming loaded.
  - `naming_input.jsonl`, `naming_output.jsonl`: the naming context and the name.
  - `steps.jsonl`: the step stream, retry included: conversation, request,
    reply, card facts, title, spend, and a slim final payload per step. The
    driver keeps full payloads in `driver-debug.jsonl`, which is not committed.
  - `route-check-report.md` and `.json`, rebuilt by `summarize_route_check.py`
    from the committed files above.
  - A scan of every capture for credential-shaped strings found none.

## Results

| Check | English | Spanish |
| :--- | :--- | :--- |
| Card created: AAPL buy and hold at $10000, dates resolved to `2023-01-03` through `2024-12-31` | Pass | Pass |
| Input change keeps asset, strategy and dates and sets $5000 | Pass | Pass |
| Run produced a result | Pass | Pass |
| Result question answered about Apple against SPY | Pass | Provider timeout, then pass on one retry |

No follow-up misread the card, so no conversation was rerun on integration.

### The history the model received

The history the chat route loaded held every card turn in the card's
typed-facts form, and every model call that received a card turn received that
form:

```json
{"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
```

The retired sentence appears in none of the captured model request bodies.
Every interpretation call sent only the new message, because the interpreter
reads the active card from its artifact context rather than from history. The
result answer composer reads a recent-conversation window:

- English: both card turns in the form above, then the run's result text.
- Spanish retry: the second card turn in the form above, the run's result text,
  and the first attempt's stored English fallback line. The first card turn was
  outside the window.

Both answered from the stored run facts (benchmark gap of 46.3 percentage
points). The first Spanish attempt's composer request was cancelled at its
25-second timeout; the capture wrapper records only requests that return or
raise an ordinary error, so that body is not in `model_requests.jsonl`.

### Naming

Naming ran once per conversation, right after the first card turn, and read
that card turn in the same typed-facts form, as the history line and as
`latest_assistant`. The titles were "Apple Buy and Hold Backtest" and "Backtest
de Apple comprar y mantener". Later turns, including the edited cards, skipped
naming because the conversations already had titles.

### Replies to the result question

- English: "Compared with SPY, this test's results show Apple beat the
  benchmark by 46.3 percentage points over the full period. Apple's total return
  on the starting capital was 100.2%, while SPY's benchmark return was 53.9%."
- Spanish, first attempt: the answer composer (`deepseek/deepseek-v4-flash`)
  timed out after 25 seconds, so the turn returned the typed retryable code
  `latest_result_followup_unavailable`. Its stored English text is the
  compatibility fallback that the Spanish interface renders from the code.
  Interpretation had routed the question exactly as in English.
- Spanish, one retry in the same conversation: "Esta prueba muestra que AAPL
  superó a SPY por 46.3 puntos porcentuales en rendimiento total durante el
  período completo."

## Spend

Billed $0.162 against the $0.50 cap: $0.151 for the two conversations and
$0.011 for the retry. Eight receipts carried no price: seven naming receipts
that skipped because a title already existed, and the timed-out call. The driver
counted each unpriced receipt at $0.02, a ceiling of $0.322, and checked the cap
before every step. No research calls ran.

## Limits

- Memory persistence and mock auth, not Supabase. The chat route, runtime,
  history loader and naming are the branch code.
- Two conversations, one path each. A live check samples behavior; it does not
  measure it.
- The retry's history includes the first attempt's stored fallback line, as a
  real retry would. A recovery turn's stored English fallback text reaching the
  composer's history in a Spanish conversation predates this change and is
  outside it.

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
