# Decision 10: forward-looking and valuation questions are answered

Founder decision of 2026-09-10, recorded in
`docs/specs/argus-grounded-finance-roadmap.md` as decision 10: Argus answers
"what will $10,000 in NVDA be worth in ten years?" and "what price does NVDA
need to grow into?" the way Perplexity does, with cited forecasts, analyst
targets and valuation multiples, the arithmetic written out, and results as
labeled scenario ranges. Never one number as the future, never advice. The one
thing that stays impossible is a backtest over a future window, because that
market data does not exist.

Lane branch `claude/argus-forward-valuation-d2289e`, base integration
`d0884c3d`. This folder holds the before picture at that base, the after
picture at the lane head, the live measurement scorecard the prompt
fingerprint now names, the browser proof, and the drivers that produced them.

## What changed

- `src/argus/agent_runtime/interpreter/unsupported_admission.py`: the clause
  that told every interpretation to classify a future-value question as
  unsupported is replaced by `future_test_window_capability_clause()`, which
  sends forward-looking and valuation questions to research and keeps only a
  test asked over a future window on the strategy route. The forced strategy
  route for a typed future horizon (`strategy_route_flags_with_future_precedence`)
  is deleted.
- `src/argus/agent_runtime/interpreter/research_routing.py`: a strategy claim
  whose horizon points forward is not a runnable test, so it no longer outranks
  a question payload; when that waiver decides the route it is recorded as
  `research_answers_future_horizon_question` on the interpretation and logged.
- `src/argus/agent_runtime/llm_interpreter.py`: the valuation paragraph no
  longer steers valuation language toward a backtest proxy; the proxy is
  offered only when the user wants to test a rule built on valuation.
- `src/argus/agent_runtime/research_grounded.py`: the research prompt asks for
  labeled scenarios built from cited inputs with the arithmetic shown, keeps
  "never estimate a live number" and "No investment advice", and can run
  without the provider's finance tool; `research_answer.py` grounds a claim
  about crypto or a currency pair on public pages that way instead of
  degrading it to a coverage note.
- `src/argus/agent_runtime/research_rows.py`: after an answer about a named
  moving-average crossover, the rows offer that idea's historical test beside
  the plain hold (the benchmark on the resulting card is the "or that money in
  the market" contrast).
- The surviving `future_performance` recovery copy (backend fallback, both
  locales) names the missing data and offers the historical test and the
  analyst research; nothing says "I can't predict".
- Measurement: the three cases that required the refusal now expect a
  published research answer with at least one next-experiment row and a new
  `scenario_framing` prose criterion (rubric v3).
- Canon: `docs/PRODUCT.md` section 11 and `docs/API_CONTRACT.md`.

## Cost estimate (posted before any paid run)

| Run | Turns | Estimate |
| --- | ---: | ---: |
| Before picture, integration `d0884c3d`: 13 questions in `drivers/questions.json` (the founder's two in en and es-419, six Driven-style, two consumer projections, the golden cross measurement case) plus the two founder questions asked of Perplexity as typed | 15 | $2.00 to $3.50 |
| After picture, lane head: the same 13 questions | 13 | $2.00 to $3.50 |
| Live measurement, full suite of 69 cases (the fingerprint scorecard must carry every case; the last full run cost $1.11 on OpenRouter plus research turns) | 69 | $1.50 to $2.50 |
| Browser proof: reuses the after-picture conversations, no new provider turns | 0 | $0 |
| **Total** | | **$5.50 to $9.50** |

Step 1 alone is the first row. The research turns dominate: a balanced turn
recorded $0.05 to $0.16 and a thorough one (the comparison and the deep dive)
runs the opus tier in the background.

## The before picture

Pending founder approval of the spend.

## The after picture

Pending.

## Live measurement

Pending.

## Browser proof

Pending.

## The founder's side by side

Ask both products the same two questions, in the same session, and compare.

1. Argus, local at the lane head. From the lane worktree:

   ```bash
   D10_TREE="$PWD" D10_ENV_FILE="$PWD/.env" poetry run python docs/reports/evidence/decision-10/drivers/serve.py
   ```

   In a second terminal, the web app against it (mock auth, Spanish on,
   research rail on):

   ```bash
   cd web && NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8610/api/v1 NEXT_PUBLIC_MOCK_AUTH=true NEXT_PUBLIC_ENABLE_SPANISH=true NEXT_PUBLIC_RESEARCH_RAIL_ENABLED=true bun run dev -- -p 3610
   ```

   Open `http://127.0.0.1:3610/chat`, start a new chat, and type each question
   exactly:

   - `what will $10,000 in NVDA be worth in ten years?`
   - `What price does NVDA need to grow into?`

   Argus should answer each with cited scenarios (bear, base, bull or similar
   labels), the arithmetic written out, a sources drawer, and a "Test ..."
   row underneath. It must not say it cannot predict, and it must not tell you
   to buy, sell or hold.

2. Perplexity. Open `https://www.perplexity.ai`, start a new thread, and type
   the same two questions exactly. Compare: does each side cite its inputs,
   show the math, label the result as scenarios, and refrain from advice?

3. The API equivalent of step 2, question as typed with no Argus prompt:

   ```bash
   D10_TREE="$PWD" D10_ENV_FILE="$PWD/.env" poetry run python docs/reports/evidence/decision-10/drivers/perplexity_plain.py nvda-future-value "what will $10,000 in NVDA be worth in ten years?" temp/perplexity-nvda-future-value.json
   ```

If Argus says it cannot do something Perplexity just did, the lane is not
done.
