# Route check report

Built by `summarize_route_check.py` from the committed capture files; figures cover only what those files record.

Server source head `4e89d289d329f7115edf1b94856c2208fd81cafa`; working tree changes under src or web: False.

## Totals

- captured_model_requests: 29
- captured_model_requests_by_host: {"openrouter.ai": 29}
- captured_model_requests_by_status: {"200": 29}
- captured_model_requests_containing_a_typed_card_turn: 4
- captured_model_requests_containing_the_retired_sentence: 0
- receipts: 37
- receipts_by_task_and_outcome: {"asset_mention_preflight: succeeded": 7, "chat_composer: failed": 1, "chat_composer: succeeded": 2, "interpretation: succeeded": 16, "name_suggestion: skipped": 7, "name_suggestion: succeeded": 2, "result_summary: succeeded": 2}
- priced_receipts_usd: 0.161836
- unpriced_receipts: 8
- research_cost_records: 0
- priced_research_costs_usd: 0
- captured_history_loads_by_reader: {"chat_route": 9, "artifact_naming": 2}
- captured_history_assistant_items: {"total": 18, "typed_card_facts": 14, "empty": 0, "containing_the_retired_sentence": 0}
- naming_inputs: 2
- naming_outputs: 2

## Checks

- PASS (en) card step: latest card has symbols [AAPL], strategy buy_and_hold and capital 10000
- PASS (en) change step: latest card is a new card turn with the same symbols, strategy and dates and capital 5000
- PASS (en) run step: final payload carries a run
- PASS (en) result_question step: reply mentions SPY and Apple or AAPL, and the final payload carries no recovery
- PASS (es-419) card step: latest card has symbols [AAPL], strategy buy_and_hold and capital 10000
- PASS (es-419) change step: latest card is a new card turn with the same symbols, strategy and dates and capital 5000
- PASS (es-419) run step: final payload carries a run
- FAIL (es-419) result_question step: reply mentions SPY and Apple or AAPL, and the final payload carries no recovery
- PASS (es-419) result_question_retry step: reply mentions SPY and Apple or AAPL, and the final payload carries no recovery

## en / card

Request: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
Title after the step: Apple Buy and Hold Backtest (ai_generated)
Reply: 
Latest card: {"message_id": "f0ad726a-655c-4a52-ae68-2c966b6dad95", "confirmation_id": "confirmation-34bfa80a-1b56-406d-8524-115870a2f51c", "strategy_type": "buy_and_hold", "symbols": ["AAPL"], "date_range": {"start": "2023-01-03", "end": "2024-12-31"}, "capital": 10000.0, "status": "ready_to_run"}
History loaded by chat_route:
History loaded by artifact_naming:
  - user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Naming input (messages):
  Name this Argus conversation from the meaningful chat context.
  user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
  assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  latest_user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
  latest_assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  Avoid generic titles like New idea.
Naming output: Apple Buy and Hold Backtest (en)
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
Captured model request to google/gemini-2.5-flash-lite (status 200), non-system messages, first 600 characters each:
  - user: Name this Argus conversation from the meaningful chat context.
user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
latest_user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
latest_assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Avoid generic titles like New idea.

## en / change

Request: Actually, make it $5000 instead.
Title after the step: Apple Buy and Hold Backtest (ai_generated)
Reply: 
Latest card: {"message_id": "461d5fab-1ecd-4142-8911-23ff78c20e8a", "confirmation_id": "confirmation-319bdaa4-ac56-4346-92dd-a81d582b6c46", "strategy_type": "buy_and_hold", "symbols": ["AAPL"], "date_range": {"start": "2023-01-03", "end": "2024-12-31"}, "capital": 5000.0, "status": "ready_to_run"}
History loaded by chat_route:
  - user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Actually, make it $5000 instead.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Actually, make it $5000 instead.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Actually, make it $5000 instead.

## en / run

Request: run_backtest
Title after the step: Apple Buy and Hold Backtest (ai_generated)
Reply: 
Latest card: {"message_id": "461d5fab-1ecd-4142-8911-23ff78c20e8a", "confirmation_id": "confirmation-319bdaa4-ac56-4346-92dd-a81d582b6c46", "strategy_type": "buy_and_hold", "symbols": ["AAPL"], "date_range": {"start": "2023-01-03", "end": "2024-12-31"}, "capital": 5000.0, "status": "ready_to_run"}
Run: {"id": "b99d2137-8a30-5eb8-8b13-6e5e07232ee9", "status": "completed", "symbols": ["AAPL"]}
History loaded by chat_route:
  - user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  - user: Actually, make it $5000 instead.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Captured model request to openai/gpt-5.6-luna (status 200), non-system messages, first 600 characters each:
  - user: {"run_facts": {"symbols": ["AAPL"], "benchmark_symbol": "SPY", "benchmark_comparison_claim": "beat_benchmark", "facts": {"portfolio.metrics.performance.return_basis": {"value": "fixed_capital", "unit": "text", "meaning": "Stored metric; definition unavailable. Do not infer its financial meaning."}, "portfolio.total_return": {"value": 100.2, "unit": "percent", "meaning": "Historical return for the complete test window", "display": "100.2%"}, "portfolio.benchmark_return": {"value": 53.9, "unit": "percent", "meaning": "Benchmark historical total return for the same window and funding plan", "disp...

## en / result_question

Request: How did that do compared to SPY?
Title after the step: Apple Buy and Hold Backtest (ai_generated)
Reply: Compared with SPY, this test's results show Apple beat the benchmark by 46.3 percentage points over the full period. Apple's total return on the starting capital was 100.2%, while SPY's benchmark return was 53.9%. So the $5,000 grew to $10,010, and the extra gain over SPY came with a bumpier ride, as the worst drop from a prior high was 16.8%. That drop began December 14, 2023, and ended April 19, 2024, with the portfolio falling $1,326 from $7,917 to $6,591 before recovering. The test can show how this specific buy-and-hold strategy performed against SPY over those dates, but it does not explain why Apple moved that way or predict future performance.
Latest card: {"message_id": "461d5fab-1ecd-4142-8911-23ff78c20e8a", "confirmation_id": "confirmation-319bdaa4-ac56-4346-92dd-a81d582b6c46", "strategy_type": "buy_and_hold", "symbols": ["AAPL"], "date_range": {"start": "2023-01-03", "end": "2024-12-31"}, "capital": 5000.0, "status": "ready_to_run"}
History loaded by chat_route:
  - user: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  - user: Actually, make it $5000 instead.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  - user: Run backtest
  - assistant: Buying AAPL once and holding it through this run turned $5,000 invested into a $5,010 gain, beating SPY by 46.3 percentage points. The tradeoff was a bumpier ride: the investment fell 16.8% from its December 2023 high to its April 2024 low before recovering.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: How did that do compared to SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: How did that do compared to SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: How did that do compared to SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: How did that do compared to SPY?
Captured model request to deepseek/deepseek-v4-flash (status 200), non-system messages, first 600 characters each:
  - user: product_language: en

Recent conversation, oldest first:
Reader: Backtest buying and holding Apple from January 2023 through December 2024 with $10000.
Argus: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Reader: Actually, make it $5000 instead.
Argus: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Reader: Run backtest
Argus: Buying AAPL once and holding it through this run turned $5,000 invested into a $5,010 gain, beating SPY by ...

## es-419 / card

Request: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
Title after the step: Backtest de Apple comprar y mantener (ai_generated)
Reply: 
Latest card: {"message_id": "fd225c69-6ab5-4afb-8eca-241da0f7d830", "confirmation_id": "confirmation-632a643c-4b55-423f-a69b-eee30ae9331b", "strategy_type": "buy_and_hold", "symbols": ["AAPL"], "date_range": {"start": "2023-01-03", "end": "2024-12-31"}, "capital": 10000.0, "status": "ready_to_run"}
History loaded by chat_route:
History loaded by artifact_naming:
  - user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Naming input (messages):
  Name this Argus conversation from the meaningful chat context.
  user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
  assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  latest_user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
  latest_assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  Avoid generic titles like New idea.
Naming output: Backtest de Apple comprar y mantener (es-419)
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
Captured model request to google/gemini-2.5-flash-lite (status 200), non-system messages, first 600 characters each:
  - user: Name this Argus conversation from the meaningful chat context.
user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
latest_user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
latest_assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Avoid generic tit...

## es-419 / change

Request: Mejor que sean 5000 dólares.
Title after the step: Backtest de Apple comprar y mantener (ai_generated)
Reply: 
Latest card: {"message_id": "5687e882-7e5b-467b-a7c8-7ebc60326047", "confirmation_id": "confirmation-f28e2464-0165-402a-9239-df0653889afc", "strategy_type": "buy_and_hold", "symbols": ["AAPL"], "date_range": {"start": "2023-01-03", "end": "2024-12-31"}, "capital": 5000.0, "status": "ready_to_run"}
History loaded by chat_route:
  - user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Mejor que sean 5000 dólares.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Mejor que sean 5000 dólares.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: Mejor que sean 5000 dólares.

## es-419 / run

Request: run_backtest
Title after the step: Backtest de Apple comprar y mantener (ai_generated)
Reply: 
Latest card: {"message_id": "5687e882-7e5b-467b-a7c8-7ebc60326047", "confirmation_id": "confirmation-f28e2464-0165-402a-9239-df0653889afc", "strategy_type": "buy_and_hold", "symbols": ["AAPL"], "date_range": {"start": "2023-01-03", "end": "2024-12-31"}, "capital": 5000.0, "status": "ready_to_run"}
Run: {"id": "e8c27e96-db72-57fe-b7c5-3c23b8992021", "status": "completed", "symbols": ["AAPL"]}
History loaded by chat_route:
  - user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  - user: Mejor que sean 5000 dólares.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Captured model request to openai/gpt-5.6-luna (status 200), non-system messages, first 600 characters each:
  - user: {"run_facts": {"symbols": ["AAPL"], "benchmark_symbol": "SPY", "benchmark_comparison_claim": "beat_benchmark", "facts": {"portfolio.metrics.performance.return_basis": {"value": "fixed_capital", "unit": "text", "meaning": "Stored metric; definition unavailable. Do not infer its financial meaning."}, "portfolio.total_return": {"value": 100.2, "unit": "percent", "meaning": "Historical return for the complete test window", "display": "100.2%"}, "portfolio.benchmark_return": {"value": 53.9, "unit": "percent", "meaning": "Benchmark historical total return for the same window and funding plan", "disp...

## es-419 / result_question

Request: ¿Cómo le fue frente a SPY?
Title after the step: Backtest de Apple comprar y mantener (ai_generated)
Reply: I couldn’t answer that follow-up. Your result is still here.
Recovery: {"code": "latest_result_followup_unavailable", "retryable": true}
Receipt not succeeded or skipped: {"task": "chat_composer", "model": "deepseek/deepseek-v4-flash", "outcome": "failed", "failure_mode": "TimeoutError", "usage_cost_usd": null}
Latest card: {"message_id": "5687e882-7e5b-467b-a7c8-7ebc60326047", "confirmation_id": "confirmation-f28e2464-0165-402a-9239-df0653889afc", "strategy_type": "buy_and_hold", "symbols": ["AAPL"], "date_range": {"start": "2023-01-03", "end": "2024-12-31"}, "capital": 5000.0, "status": "ready_to_run"}
History loaded by chat_route:
  - user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  - user: Mejor que sean 5000 dólares.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  - user: Ejecutar backtest
  - assistant: Comprar AAPL una vez y mantenerla durante este periodo terminó con una ganancia de $5,010 sobre el capital invertido. Superó a SPY por 46.3 puntos porcentuales, pero el recorrido tuvo una caída máxima de 16.8% antes de recuperar terreno. En resumen, mantener la posición ofreció más crecimiento que el benchmark, a cambio de aceptar una experiencia más irregular.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?

## es-419 / result_question_retry

First attempt's recovery: {"code": "latest_result_followup_unavailable", "retryable": true}
Request: ¿Cómo le fue frente a SPY?
Reply: Esta prueba muestra que AAPL superó a SPY por 46.3 puntos porcentuales en rendimiento total durante el período completo. La prueba no almacena cómo se comportó mes a mes frente al referencia, solo la diferencia final. Si quieres ver cómo se compara en otros aspectos, podemos revisar la volatilidad o probar una estrategia diferente.
History loaded by chat_route:
  - user: Haz un backtest de comprar y mantener Apple desde enero de 2023 hasta diciembre de 2024 con 10000 dólares.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  - user: Mejor que sean 5000 dólares.
  - assistant: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
  - user: Ejecutar backtest
  - assistant: Comprar AAPL una vez y mantenerla durante este periodo terminó con una ganancia de $5,010 sobre el capital invertido. Superó a SPY por 46.3 puntos porcentuales, pero el recorrido tuvo una caída máxima de 16.8% antes de recuperar terreno. En resumen, mantener la posición ofreció más crecimiento que el benchmark, a cambio de aceptar una experiencia más irregular.
  - user: ¿Cómo le fue frente a SPY?
  - assistant: I couldn’t answer that follow-up. Your result is still here.
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?
Captured model request to x-ai/grok-4.3 (status 200), non-system messages, first 600 characters each:
  - user: ¿Cómo le fue frente a SPY?
Captured model request to deepseek/deepseek-v4-flash (status 200), non-system messages, first 600 characters each:
  - user: product_language: es-419

Recent conversation, oldest first:
Reader: Mejor que sean 5000 dólares.
Argus: {"confirmation_card":{"strategy_type":"buy_and_hold","symbols":["AAPL"],"date_range":{"start":"2023-01-03","end":"2024-12-31"}}}
Reader: Ejecutar backtest
Argus: Comprar AAPL una vez y mantenerla durante este periodo terminó con una ganancia de $5,010 sobre el capital invertido. Superó a SPY por 46.3 puntos porcentuales, pero el recorrido tuvo una caída máxima de 16.8% antes de recuperar terreno. En resumen, mantener la posición ofreció más crecimiento que el benchmark, a cambio de aceptar ...
