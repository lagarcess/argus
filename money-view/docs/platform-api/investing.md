# Investing API (stable contract)

All paths start with `/api/platform/investing`. The active user and household
come from `common.Context`; callers never supply either identifier. All money
amounts and quantities are decimal strings. Currencies are kept separate. All
market figures carry dated `Evidence`; the bundled market data is visibly
synthetic and dated `2026-09-20`.

This surface is a paper-investing simulator. It has no broker connection or
order-execution capability. Linked investment accounts are read from the
ledger's public `account_balances()` query and shown separately. Manual
holdings here represent alternative assets outside those accounts. Simulated
cash and positions are fictional and are excluded from household net worth.

## Portfolio and manual alternative holdings

`GET /portfolio` returns:

```json
{
  "as_of": "2026-09-20",
  "linked_accounts": [{"id":"acct-demo-06","name":"Demo investments","currency":"USD","balance":"24500.00","source":{}}],
  "alternative_holdings": [{
    "id":"holding-demo-gold","symbol":"ALT-GOLD","name":"Gold certificate",
    "quantity":"2","currency":"USD","total_cost":"3600.00","as_of":"2026-09-20",
    "price":{"symbol":"ALT-GOLD","currency":"USD","price":"1950.00","as_of":"2026-09-20","source":{}},
    "market_value":"3900.00","gain_loss":"300.00","gain_loss_pct":"8.3333",
    "allocation_pct":"100.0000","source":{}
  }],
  "totals":[{
    "currency":"USD","linked_accounts":"24500.00","priced_alternatives":"3900.00",
    "portfolio_value":"28400.00","alternative_cost_basis":"3600.00",
    "alternative_gain_loss":"300.00","alternative_gain_loss_pct":"8.3333",
    "is_partial":false,"unpriced_holding_ids":[],"source":{}
  }],
  "net_worth_additions":[{"currency":"USD","amount":"3900.00","source":{}}],
  "benchmarks":[{
    "id":"benchmark-spy","symbol":"SPY","name":"Synthetic broad US market example",
    "currency":"USD","start_on":"2025-09-20","end_on":"2026-09-20",
    "start_price":"590.00","end_price":"650.00","return_pct":"10.1695","source":{}
  }],
  "simulation": {
    "books":[{"id":"book-demo-usd","name":"USD learning book","currency":"USD","cash":"10000.00","initial_cash":"10000.00","source":{}}],
    "positions":[{
      "book_id":"book-demo-usd","symbol":"AAPL","currency":"USD","quantity":"2",
      "total_cost":"460.00","average_cost":"230.00",
      "price":{"symbol":"AAPL","currency":"USD","price":"230.00","as_of":"2026-09-20","source":{}},
      "market_value":"460.00","gain_loss":"0.00","gain_loss_pct":"0.0000","source":{}
    }],
    "recent_orders":[]
  },
  "source": {}
}
```

`net_worth_additions` is the only investing value a household overview should
add to ledger net worth. Linked account balances are already in the ledger;
simulation values are fictional. When a holding has no price, its value is
omitted, its ID is listed in `unpriced_holding_ids`, and `is_partial` is true.

`GET /holdings` returns `{items:[holding...]}`. `POST /holdings` accepts
`{symbol,name,quantity,total_cost,currency,as_of}`. `PATCH /holdings/{id}`
accepts any non-empty subset of `name,quantity,total_cost,as_of`. `DELETE
/holdings/{id}` returns `{id,deleted:true}`. Writes require editor or owner.
Symbols are uppercase letters, digits, dot or hyphen, 1 to 24 characters.

## Alternative-holding CSV

`GET /holdings/sample.csv` returns a template with header
`symbol,name,quantity,total_cost,currency,as_of`.

`POST /holding-imports/preview` accepts
`{"csv":"symbol,name,quantity,total_cost,currency,as_of\nALT-CARD,Card collection,1,1200.00,USD,2026-09-20\n"}`
and returns
`{id,rows:[{line,symbol,name,quantity,total_cost,currency,as_of,duplicate}],errors:[{line,code}],valid_count,duplicate_count,can_commit,source}`.
Maximum input is 1 MB and 2,000 rows. Existing or repeated symbol/currency
pairs are marked duplicate and are not imported. Preview never changes a
holding.

`POST /holding-imports/{id}/commit` accepts
`{"idempotency_key":"alternative-import-1"}` and returns
`{id,imported,duplicates,holding_ids,source}`. A replay with the same key and
preview returns the original receipt. Reusing a key for another preview returns
409 `idempotency_conflict`.

## Market data load

`POST /prices/load` accepts `{"outcome":"success"|"failure"}` and returns
`{id,status,as_of,completed_at,error_code,source}`. It invokes only the local
fixture adapter. `as_of` and `source` are null on failure. A failed attempt
keeps the prior last-good prices. The same
`load_market_prices(store, adapter)` function is the scheduled/manual job seam.
No request-time vendor polling occurs.

The browser route remains fixture-only. A real Alpaca read uses the local CLI,
so no page view or API request can trigger a vendor call:

```sh
# Default fixture adapter, no credentials needed.
.venv/bin/python -m server.platform.market_job load \
  --database .local/clara.sqlite3 --symbols AAPL,SPY

# Read-only Alpaca Market Data. This performs exactly one HTTP GET.
CLARA_ALPACA_API_KEY=... CLARA_ALPACA_API_SECRET=... \
.venv/bin/python -m server.platform.market_job load --provider alpaca \
  --database .local/clara.sqlite3 --symbols AAPL,SPY --feed iex
```

The adapter has one fixed destination:
`https://data.alpaca.markets/v2/stocks/bars/latest`. It sends explicit
comma-separated symbols, `currency=USD`, and an explicit feed. `iex` is the
default because Alpaca documents it as the Basic-plan equities feed. It reads
the latest minute bar's `c` close and `t` timestamp, requires every requested
symbol on one UTC observation date, and stores the result as published dated
evidence. It follows no redirects and performs no automatic retries. Partial,
malformed, stale-date-mixed, nonpositive, unauthorized, rate-limited, or
oversized responses fail the load and retain the last good price set.

Only `CLARA_ALPACA_API_KEY` and `CLARA_ALPACA_API_SECRET` are read, and only by
the CLI. The HTTP adapter receives them explicitly. It never reads Alpaca SDK,
Argus, parent-process naming conventions, or a configurable destination. It
contains no broker, account, order, or trading endpoint.

Official references:

- [Alpaca latest bars](https://docs.alpaca.markets/us/reference/stocklatestbars-1)
- [Alpaca Market Data authentication](https://docs.alpaca.markets/us/v1.1/docs/about-market-data-api#authentication)
- [Alpaca official OpenAPI latest-bars example](https://github.com/alpacahq/alpaca-docs/blob/master/oas/data/openapi.yaml)

## Paper orders

`GET /books` returns
`{items:[{id,name,currency,cash,initial_cash,source}]}`. Demo books use fictional
cash. `GET /orders?limit=20` returns immutable confirmed receipts newest first.
`simulation.recent_orders` uses that same confirmed-receipt shape, limited to
the 10 newest records. An unpriced simulation position has `price`,
`market_value`, `gain_loss`, and `gain_loss_pct` set to null.

`POST /orders/preview` accepts one of:

```json
{"book_id":"book-demo-usd","side":"buy","symbol":"AAPL","quantity":"2"}
{"book_id":"book-demo-usd","side":"sell","symbol":"AAPL","quantity":"1"}
{"book_id":"book-demo-usd","side":"buy","bundle_id":"bundle-steady-three","amount":"1000.00"}
```

It returns an immutable quote snapshot:

```json
{
  "id":"preview-...","book_id":"book-demo-usd","side":"buy",
  "kind":"symbol","symbol":"AAPL","bundle_id":null,"currency":"USD",
  "legs":[{"symbol":"AAPL","quantity":"2","price":"230.00","gross":"460.00","price_as_of":"2026-09-20","price_source":{}}],
  "gross":"460.00","fee":"0.00",
  "rounding_rule":"buy_ceiling_sell_floor","rounding_cost":"0",
  "cash_effect":"-460.00",
  "quoted_at":"2026-09-20T...Z","expires_at":"2026-09-20T...Z","source":{}
}
```

`POST /orders/{preview_id}/confirm` accepts
`{"idempotency_key":"paper-order-1"}` and returns
`{id,preview_id,book_id,side,kind,symbol,bundle_id,currency,legs,gross,fee,rounding_rule,rounding_cost,cash_effect,cash_before,cash_after,confirmed_at,source}`.
Confirmation runs under one SQLite write lock. Replays return the same receipt;
concurrent double clicks create one receipt. It returns `stale_quote` when the
preview expired or a newer price snapshot exists, `insufficient_simulated_cash`
for an unaffordable buy, and `insufficient_simulated_quantity` for an oversell.

`gross` is the amount settled against fictional cash. One shared rule rounds a
buy up and a sell down to the currency's minor unit. `rounding_rule` is always
`buy_ceiling_sell_floor`; `rounding_cost` is the exact nonnegative difference
between price-times-quantity and settled gross and may contain sub-minor digits.
Both fields appear on previews and immutable receipts. Orders whose exact gross
is less than one currency minor unit return `order_amount_too_small`. The rule
applies to symbol, bundle, and recurring orders, so splitting a round trip at an
unchanged price cannot increase simulated cash.

## Recurring simulations and bundles

`GET /bundles` returns `{items:[{id,name,description,currency,legs:[{symbol,weight_pct}],source}]}`.
Bundles are curated synthetic learning examples, not recommendations. They may
only be bought in the simulator.

`GET /recurring-plans` returns `{items:[plan...]}`. `POST /recurring-plans`
accepts either a symbol purchase or bundle purchase:

```json
{"book_id":"book-demo-usd","cadence":"monthly","next_run_on":"2026-09-20","symbol":"AAPL","amount":"250.00"}
{"book_id":"book-demo-usd","cadence":"weekly","next_run_on":"2026-09-20","bundle_id":"bundle-steady-three","amount":"300.00"}
```

It returns `{id,book_id,cadence,next_run_on,symbol,bundle_id,amount,currency,active,source}`.
`PATCH /recurring-plans/{id}` accepts any non-empty subset of
`amount,next_run_on,active`. `POST /recurring-plans/{id}/run` accepts
`{"run_on":"2026-09-20"}` and returns
`{id,plan_id,period_key,run_on,status,order_receipt,error_code,source}`. A plan
can attempt at most once per ISO week or calendar month. Repeating the call in
that period returns the same run record and never places a second paper order.
Any current household editor or owner may manually update or run a shared plan,
including one created by another member.

## Python query helpers

`portfolio_summary(store: Store, context: Context) -> dict` returns exactly
`GET /portfolio` and is the grounded assistant hook. Consumers must use its
`net_worth_additions` field when composing household net worth.

`run_due_recurring_plans(store, run_on, *, cursor=None, limit=100) -> dict` is
the scheduled local simulation hook. It returns:

```json
{
  "items": [{"id":"recurring-run-...","status":"succeeded","order_receipt":{},"error_code":null}],
  "next_cursor": "opaque-or-null",
  "next_poll_on": "2026-09-27"
}
```

The indexed due query orders by `next_run_on,id`, reads at most `limit + 1`
rows, and accepts only `1..100`; 100 is the default and hard maximum. A
continuation job supplies the opaque cursor (at most 512 characters) only when
`next_cursor` is not null. `next_poll_on` is the earliest next date among active plans, or null when
none remain. Invalid inputs return `invalid_recurring_cursor` or
`invalid_recurring_limit`.

Before each scheduled attempt, the helper rereads the creator and household
membership. The creator must still be an active user with owner or editor
permission. A deleted, removed, or demoted creator causes one failed run with
`recurring_creator_unauthorized` and pauses the plan; no paper order is made.
This creator check applies only to background dispatch. It does not prevent a
current household editor from manually managing another member's shared plan.

The durable run and immutable order receipt use the same
`recurring:{plan_id}:{period_key}` idempotency key. On replay, a confirmed
receipt finalizes the run and advances the plan. A running record older than
the 30-second domain lease with no receipt becomes
`recurring_run_interrupted` and advances without placing an order. This keeps
dispatch and retry ownership in the shared operational job queue while the
investing domain reconciles its own receipt. A crashed attempt cannot remain
`running` forever. The hook remains household scoped, uses only fictional
simulation cash, and never calls a broker.

Recurring confirmation passes its run ID into the shared settlement function.
After receipt replay checks, settlement verifies under the same SQLite write
transaction that the run is still `running`, the plan is active, the book
matches, and the idempotency key names that plan and cadence period. A recovered
or paused run returns `recurring_settlement_not_authorized` before cash or
positions change. A receipt committed before recovery still wins during
reconciliation.
