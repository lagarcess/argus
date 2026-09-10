# Real-provider browser proof

This folder records the founder-approved local browser exercise using real
Alpaca market data, Argus's real backtest engine, and configured OpenRouter
models. Authentication and persistence are local memory fixtures. No hosted
database, production deployment, or real-money order is involved.

The limit is four fresh backtest attempts and $1 total model exposure. Every
outbound completion, including normal application retries and fallback models,
is reserved before transmission. There are no outer retries or repeated cases.
Unknown response costs are conservatively charged at their full reserved cost;
`cost_usd: null` remains null rather than being called free.

The first English DOCN case ran on
`c36c099316578fb03804405f24cc1600debd0f25`. Its original ledger, receipts,
messages, source manifest, and browser result are preserved in `initial-c36/`.
The Spanish DOCN case used
`1fbeeaced804f4523c20c93cc4d7db176a48c006`, which removed provider provenance
metadata from shared model facts. DCA's first setup used `e2793800`, while its
single clarification reply, the RSI browser run, and the new old-run Breakdown
used `104da766a88d04fc466285a64c622b936925d657`. Each checkpoint and the cumulative
ledger preserve these distinct creation sources. The fourth direct DCA engine
fixture is pending the captain's clean commit; it has not run yet.

The first case completed one genuine engine run and accepted the configured
Qwen fallback's Quick take after DeepSeek timed out. Its Breakdown is a template:
the first harness halted on an HTTP400 without usage and interrupted the
application's ordinary retry. This is evidence of visible fallback behavior,
not a valid negative quality judgment about a completed Breakdown draft.
The original HTTP400 body was not retained, so its cause is unknown.

The initial guard retained the canceled DeepSeek attempt's dollar reservation,
but its `Exception` handler missed `asyncio.CancelledError`. The original ledger
therefore shows attempt6 as `in_flight`; the matching Argus receipt records a
30005ms timeout. The revised harness catches cancellation and separately charges
all unknown costs at their full reservation, allowing the normal application
retry within the same budget. The original reported cost was $0.02436845, and
the two conservative charges totaled $0.04329132. Four offline budget tests
passed before resuming. `initial-c36/budget-loaded.py` reconstructs the initially
loaded guard by reversing the two unexecuted post-stop diagnostic edits.

`readonly-recovery.json` records four first-case saved states: English match and
reload, then Spanish mismatch and reload. Both frames are visible in their PNGs,
and model-attempt count remained nine throughout. The accepted English Quick
take is replaced by today's Spanish template on mismatch. There were no browser
console errors in these captures.

`stored-runs/docn-en.json` is a full sanitized freshly executed run.
`stored-runs/old-run-new-breakdown.json` is a separate genuine previously saved
DOCN run supplied for the optional new-Breakdown acceptance. The old run has
locally reconstructed conversation/control metadata so its Explain result action
can be exercised; its metrics are not synthetic. New transport fixtures in the
sibling `browser/` replay folder are synthetic and are not live-model evidence.

For every fresh case the browser enters a fully specified idea, clicks the
confirmation's Run backtest / Ejecutar backtest, then Explain result / Explicar
resultado once. Matching-language, reload, and Settings language-switch captures
are saved without further model calls. `fee-ledger.json` owns cumulative model
attempts and backtest count across the controlled API restart. Raw readout
completion bodies, usage, selected models, and any safely redacted provider
errors are retained there. `route-receipts.json` preserves application routing
and fallback outcomes separately.

Harness entry points are `live_api.py`, `start_web.py`, and `capture.cjs`.
They require the explicit candidate SHA and go environment variables; an
existing ledger requires explicit same-allowance resume. The web source is
copied into temporary storage so Next's automatic config changes cannot modify
the repository. `.env` files are read only; secrets are never recorded. Browser
external requests are blocked, and the API permits only the approved model and
market-data hosts plus localhost.

The Spanish DOCN case then completed on `1fbeeace`, bringing the cumulative
backtest count to two. Both drafts fell back. The Quick take quoted a saved
ending value that was missing from its projection, and inspection of the actual
Spanish drafts also exposed numeric-format validation defects. The normal
Breakdown retry succeeded after an HTTP400 explicitly reported that reasoning
could not be disabled. These raw drafts remain in the fee ledger. The first
Spanish match screenshot captured a streaming placeholder before completion;
that screenshot is diagnostic only, not acceptance of final text.

The DCA setup turn ran on `e2793800`, before any DCA backtest. It incorrectly
interpreted the requested starting capital as a contribution ceiling and asked
for clarification. `checkpoint-e279/` preserves that conversation, including
its canonical `pending_strategy` metadata for normal cold-checkpointer
recovery. The pending conversation is continued, not restarted. The UI showed
no option buttons despite saved typed options, so a single clarification reply
may be necessary. RSI had not started at this checkpoint.

The single DCA clarification reply on `104da766` repeated the same recovery
instead of producing confirmation. That blocked chat journey is preserved in
`dca-followup-resumed-stopped.png` and its DOM/JSON. No further DCA chat reply or
setup was issued. The separately authorized fourth engine fixture will use the
exact already approved inputs directly, with models disabled; it is not evidence
that the DCA chat journey succeeded.

RSI completed on `104da766` with a genuine stored run. Its accepted engine config
contains RSI14, thresholds30/70, the requested year, $1,000, SPY, and zero modeled
costs. Both Spanish drafts returned from models but failed validation and showed
complete templates; the actual drafts remain recorded for the later offline
numeric-format fix. No fifth backtest or fresh RSI rerun is authorized.

The optional new Breakdown on the old saved DOCN run was triggered once through
the canonical local `show_breakdown` API action because the sparse old card did
not expose its button. The model completed through its normal reasoning-setting
retry, and the newly persisted envelope is stamped `es-419`. Its draft failed
validation, so the complete Spanish template is visible. This is an actual new
composition attempt on an old run, not a successful visible-button journey or an
accepted model-quality sample. No saved readout was rewritten.

`final-saved-proof.json` records12 saved states across the three successful
browser backtests, with language match/mismatch and reload, visible-copy parity,
zero browser console entries, zero read-time model requests, and no mobile
horizontal overflow. Matching the first English DOCN shows its accepted model
Quick take; every previously saved fallback remains a fallback. Development-only
font preload warnings from the preliminary sparse-old-card setup are preserved
in `old-run-button-unavailable.json`; the final saved matrix has none.

The final browser viewer used the copied reader source from `104da766`; earlier
creation SHAs remain attached to each run in the cumulative fee ledger. The
reader source hashes are in `web-source.json`. `cleanup.json` records stopped
servers and removed isolated web copies. The only remaining execution is the
fourth direct DCA engine fixture after the captain supplies its clean source SHA.
The terminal manifest will record its result and final total.

For the founder's PR-preview side-by-side, set Settings → Preferences → App
language → English. In a new chat, submit:

> Buy and hold DOCN from September 1, 2023 through September 9, 2026 with $1,000 starting capital, against SPY. No fees or slippage.

Review the confirmation, click **Run backtest**, then **Explain result**. For
Spanish, use Ajustes → Preferencias → Idioma de la app → Español and a new chat:

> Compra y mantén DOCN del 1 de septiembre de 2023 al 9 de septiembre de 2026, con capital inicial de $1,000. Compáralo con SPY, sin comisiones ni deslizamiento.

Click **Ejecutar backtest**, then **Explicar resultado**. Compare **Quick take /
Lectura rápida** and **Breakdown / Desglose** with the competitor. These are the
actual UI labels observed here. This runbook does not claim that the earlier
saved fallback samples became accepted model readouts after later fixes.
