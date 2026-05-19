# Conversational Transcript QA

Use this script before calling the chat product ready. Run it in the live web app, not only through unit tests.

## Start The App

Backend:

```powershell
poetry run fastapi dev src/argus/api/main.py
```

Frontend:

```powershell
cd web
bun run dev
```

Recommended local settings:

- `NEXT_PUBLIC_MOCK_AUTH=true`
- `NEXT_PUBLIC_COLLECTIONS_ENABLED=false`
- `NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1`
- `OPENROUTER_API_KEY` set in backend `.env`
- Alpaca credentials set in backend `.env`
- Supabase variables set when testing persistence.

## Pass Criteria

For every transcript:

- The frontend keeps the same conversation thread.
- Argus does not repeat a generic starter opener mid-thread.
- Follow-ups refine the prior idea unless the user clearly starts a new one.
- Buy-and-hold does not ask for entry or exit logic.
- Unsupported requests are explained honestly and include an executable alternative.
- Supported runs require confirmation before execution.
- Executed runs produce a result card and a grounded assistant explanation.
- Result cards appear before summaries and expose result-only actions.
- Save Strategy is inside the result card, not in confirmation actions.
- Reloading chat preserves messages, cards, latest run state, and action availability.
- The assistant does not fabricate missing metrics.
- The result card chart renders with visible TradingView attribution in light and dark themes.

## Transcript Set

Run these in one conversation unless a case explicitly says to start a new chat:

1. `what can you do?`
2. `help me test an idea`
3. `Buy and hold Tesla over the last 2 years.`
4. `yes`
5. `Invest $500 in Bitcoin every month since 2021.`
6. `Backtest Tesla: buy when RSI drops below 30, sell when RSI rises above 55.`
7. `Actually make that weekly instead.`
8. `No, use Nvidia instead of Tesla.`
9. `Keep the same entry but change the exit.`
10. `Compare that with buy and hold.`
11. `Backtest Tesla when RSI is below 30, volume is above 1 million, and price is above the 200-day moving average.`
12. `Add a 10 percent stop loss and take profit at 20 percent.`
13. `Backtest Tesla and Bitcoin together.`
14. `What assumptions are in this backtest?`
15. `Why did this underperform SPY?`
16. `I don't know what RSI means, explain it simply.`
17. `No, I meant sell all.`
18. `Keep everything else the same.`
19. `Can you simplify this strategy so it actually runs?`
20. `Compare this to DCA.`
21. `What exactly are you testing here?`

## Launch Additions

Run these as separate focused checks after the main transcript set.

### Structured Actions

1. Create a supported buy-and-hold strategy.
2. Confirm that the confirmation card shows only `Run backtest`, `Change dates`, `Change asset`, `Adjust assumptions`, and cancel behavior.
3. Click `Run backtest`.
4. Confirm no fake user text such as `yes` or `Run backtest` is submitted.
5. Confirm the result card shows before the result summary.
6. Confirm result actions are `Show a breakdown`, `Refine strategy`, and the in-card `Save strategy` control.
7. Click `Show a breakdown` and verify the answer explains metrics, assumptions, benchmark, chart caveats, and data limits without inventing fields.
8. Click `Refine strategy` and verify Argus keeps the latest run context.

### Save Strategy And Strategies Surface

1. Run a supported backtest.
2. Click the in-card `Save strategy` control.
3. Navigate to the Strategies sidebar item.
4. Confirm the saved strategy appears with the same symbols, strategy type, period, and latest run summary.
5. Refresh the browser and confirm the saved strategy still appears.
6. Confirm collections UI remains hidden when `NEXT_PUBLIC_COLLECTIONS_ENABLED=false`.

### Persistence And Reload

1. Start a new chat and create a confirmation card.
2. Refresh the browser.
3. Confirm the confirmation card and action availability are restored.
4. Run the backtest.
5. Refresh again.
6. Confirm the result card, summary, chart, latest run id, and result actions are restored.

### Provider Truth

1. `Backtest EUR/USD over the last 3 months.`
2. Confirm Argus treats it as a currency pair and uses Kraken availability.
3. Ask for a window that exceeds Kraken's OHLC availability at the chosen interval.
4. Confirm Argus explains the 720-candle provider limit and offers a shorter window or wider timeframe.
5. `Backtest Tesla and Bitcoin together.`
6. Confirm Argus explains mixed asset classes and offers separate runs or an asset-class choice.

### Indicator Assumptions

1. `Buy Apple when RSI is below 32 and sell when RSI is above 61.`
2. Confirm the card preserves the user thresholds if the executable spec accepts them.
3. Ask `What indicator assumptions are you using?`
4. Confirm Argus answers from the executable indicator registry: period, output, allowed bounds, and defaults.
5. Try a discovered but non-executable indicator and confirm Argus drafts the idea but offers an executable simplification instead of pretending support.

### Backtest Trust

1. Run a buy-and-hold strategy.
2. Confirm the main card shows total return, final value, max drawdown, and benchmark delta.
3. Confirm win rate is hidden for buy-and-hold if closed trades are not meaningful.
4. Run a rule-based strategy with closed trades.
5. Confirm win rate appears only when there are meaningful closed trades.
6. Ask for a breakdown and confirm secondary metrics and caveats live there, not in the main card.

### Chart Behavior

1. Run a multi-symbol backtest such as `Buy and hold SBUX and CMG year to date with 100k capital.`
2. Confirm the result card universe shows all symbols.
3. Confirm the chart shows the aggregate portfolio equity curve rather than separate symbol comparison lines.
4. Hover over the chart and verify tooltip date/value/event behavior.
5. Switch light/dark/system theme and verify chart colors remain legible.
6. Run a strategy with entry/exit events and verify markers appear without clutter.

## Evidence To Capture

Record:

- Browser URL and timestamp.
- Conversation id from the network request payload.
- Any stream event error.
- Screenshot after a successful result card.
- Notes for every clarification question: was it necessary and specific?
- Notes for unsupported handling: did it preserve the user's intent?

## Known Failure Patterns To Reject

- `What is one idea or market question you want to explore first?` after the conversation has already started.
- Asking for entry logic on buy-and-hold.
- Asking for exit logic when the real issue is mixed asset support.
- Losing the prior strategy after `weekly instead`, `keep everything else`, or `use Nvidia`.
- Showing a result card while dropping the assistant explanation.
- Treating unsupported strategy drafting as a fresh empty session.
- Any one-word answer such as `AAPL`, `DCA`, or `Since IPO` when the user asked for explanation.
- Result summaries that quote the latest novice question instead of the confirmed strategy thesis.
- Result cards that drop symbols from multi-symbol runs.
- Provider errors exposed as raw exception names without natural recovery.
- TradingView chart attribution hidden or covered.
- Repeating starter guidance such as `No problem. I can help you pick a starting point` after the user has already asked to draft or test a strategy.
- Raw slot prompts such as `What should trigger the buy?` when the user's act is beginner guidance, buy-and-hold, or a complete strategy request.
- Re-asking for a period, asset, amount, cadence, or rule after the user already supplied that field in the same active strategy frame.

## Stabilization Transcript Gates

Run these before PR submission whenever conversational runtime code changes:

1. `Hey, I'm a beginner, what can you do?`
   - Pass: Argus explains how to start in plain language.
   - Reject: result metric explanations, stale run context, or generic starter reset copy.
2. `let's draft a strategy`
   - Pass: Argus invites a natural idea without forcing a form.
   - Reject: `pick a starting point`, raw field names, or entry/exit prompts.
3. `let's try a buy and hold strategy on bitcoin in the last two years, simple`
   - Pass: Argus reaches confirmation with `BTC`, `crypto`, buy-and-hold, and the two-year period resolved.
   - Reject: any request for entry logic, exit logic, or another period.
4. Start with `Let's test a buy and hold strategy`, then reply `Let's try the strategy with BTC`, then `The last two years to date`.
   - Pass: Argus applies each answer to the pending strategy frame and reaches confirmation.
   - Reject: any repeated period prompt after the final turn.
5. Start a DCA flow, provide the amount, then provide the period.
   - Pass: Argus preserves the user-provided recurring amount through later turns.
   - Reject: re-asking the amount after it was supplied.

## QA Transcript Decision Filter

When adding or updating conversational QA transcripts, ask:

> *Does this test semantic success, groundedness, and recovery rather than brittle exact wording?*

If no, the transcript likely overfits language the LLM should own.
