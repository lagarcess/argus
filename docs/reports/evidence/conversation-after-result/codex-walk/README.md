# Codex review fixes: live walk

The real web app driven by Playwright against the local live API, with automatic sign-in, memory persistence, live market data and live models. The API ran `6d988a77`. The web fix `210e14ca` was loaded by the dev server before the walk resumed. Answer text and timings for every step are in `walk-report.json`. Billed spend for the walk: $0.369.

| Check | English | Spanish |
| --- | --- | --- |
| A monthly-buy request that states 10 bps slippage shows 10 bps on the card, or Argus asks | Pass: "5 bps fee + 10 bps slippage" | **Fail:** the card shows "deslizamiento de 0 bps" and Argus did not ask |
| "What was the max drawdown?" states the stored value with no research | Pass: 44.9%, Feb 18 to Aug 1, 2025; 20 s; no research call | Pass: 44.9%, same window; 24 s; no research call |
| "When did it peak?" states the stored value with no research | Pass: June 15, 2026, $6,784; 21 s; no research call | Pass: same; 19 s; no research call |
| "Which benchmark did it use?" names the ticker | Pass: SPY | Pass: SPY |
| The card, the Quick take and an answer show the same benchmark gap | Pass: 290.0 points on the card, the Try next reason and the answer; the Quick take gives 359.4% against 69.4% | Pass: 290.0 points on the card and the answer |
| On a monthly-buy result, "when was the worst drop?" reads naturally | Pass after `210e14ca` | Pass |
| "Why did it fall so much?" researches, with sources | Pass: anchored on the worst drop, 5 sources | Not run: the spend guard stopped the walk before this step |

## What the walk found

- **A result fact the run does not store was hidden.** The first English "when was the worst drop?" answer showed the copy for rules Argus cannot run ("What rule should I test? Which supported direction should I use: …") instead of the model's answer. The typed limitation arrives as an `unsupported_recovery` intent, and the chat drew every such intent with that copy. Fixed in `210e14ca`; `monthly_buy_costs-en-03-worst-drop.png` is the same stored answer after the fix.
- **The Spanish card lost the stated slippage.** In the live turn the cost audit could not ground "deslizamiento de 10 bps", so it removed the value and owed a question (`execution_cost_evidence_unresolved`, missing `assumption`). The question was still owed after the interpreter's last logged step, yet the stage confirmed the card with the 0 bps default. Offline replays of the same message through the interpreter and the interpret stage ask the question on each path tried: a complete first reading, the focused strategy repair, and the date window repair. The live cause is not yet found.
- **Model wording to note, not changed here.** The "not stored" worst-drop answer infers that the drop came after the portfolio's peak, which the run facts do not say, and the list after it suggests asking the same question again. Both come from the model's instructions, which this round does not change.

## Files

| File | What it shows |
| --- | --- |
| `monthly_buy_costs-en-01-card.png` | English monthly-buy card with "5 bps fee + 10 bps slippage" |
| `monthly_buy_costs-en-02-result.png` | Its result: card, Quick take and Try next reason all say 206.6 points |
| `monthly_buy_costs-en-03-worst-drop.png` | "When was the worst drop?": the "not stored" answer under its fact heading |
| `monthly_buy_costs-es-419-01-card.png` | Spanish monthly-buy card showing "deslizamiento de 0 bps" (the failure above) |
| `monthly_buy_costs-es-419-02-result.png` | Its result |
| `monthly_buy_costs-es-419-03-worst-drop.png` | "¿Cuándo fue la peor caída?": the "not stored" answer |
| `buy_and_hold-en-02-result.png` | English buy and hold result: 290.0 points on the card and the Try next reason |
| `buy_and_hold-en-03-max-drawdown.png` | "What was the max drawdown?" |
| `buy_and_hold-en-04-peak.png` | "When did it peak?" |
| `buy_and_hold-en-05-benchmark.png` | "Which benchmark did it use?" |
| `buy_and_hold-en-06-benchmark-gap.png` | "How did it do against the benchmark?": 290.0 points |
| `buy_and_hold-en-07-why-it-fell.png` | "Why did it fall so much?": researched, 5 sources |
| `buy_and_hold-es-419-02-result.png` | Spanish buy and hold result |
| `buy_and_hold-es-419-03-max-drawdown.png` | "¿Cuál fue la caída máxima?" |
| `buy_and_hold-es-419-04-peak.png` | "¿Cuándo alcanzó su valor más alto?" |
| `buy_and_hold-es-419-05-benchmark.png` | "¿Qué referencia usó?" |
| `buy_and_hold-es-419-06-benchmark-gap.png` | "¿Cómo le fue frente a la referencia?": 290.0 points |
