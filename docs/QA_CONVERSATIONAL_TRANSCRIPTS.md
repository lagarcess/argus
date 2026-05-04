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
- `NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8000/api/v1`
- `OPENROUTER_API_KEY` set in backend `.env`
- Alpaca credentials set in backend `.env`

## Pass Criteria

For every transcript:

- The frontend keeps the same conversation thread.
- Argus does not repeat a generic starter opener mid-thread.
- Follow-ups refine the prior idea unless the user clearly starts a new one.
- Buy-and-hold does not ask for entry or exit logic.
- Unsupported requests are explained honestly and include an executable alternative.
- Supported runs require confirmation before execution.
- Executed runs produce a result card and a grounded assistant explanation.
- The assistant does not fabricate missing metrics.

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

