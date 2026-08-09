# Research-to-test rail evidence (#377)

Lane: `claude/research-to-test-rail`, merged forward onto integration tip
`01044cda` (2026-08-08). Spec:
`docs/superpowers/specs/2026-08-07-research-to-test-rail.md`, including the
binding section 11b amendment (one rail, not two).

## Live coverage probes (`probes/`)

Real Perplexity Agent API responses captured 2026-08-07 during the build,
because the spec instructs evidence over documentation (section 5). Raw JSON,
one file per probe.

Findings that shaped the implementation:

- `equity_control_quote.json`: the documented fast configuration
  (`max_steps=1`) returns zero `finance_search` invocations even for AAPL;
  the first step is consumed by a `skill_loaded` event and the model answers
  "I can't retrieve live market data right now."
- `equity_steps2.json`: `max_steps=2` grounds correctly (one invocation,
  AAPL close 312.41 on 2026-08-06). The shipped fast config uses 2 and the
  deviation is documented in `src/argus/domain/research/config.py`.
- `equity_steps_default.json`: omitting `max_steps` also fails to invoke the
  tool, so the default is not permissive.
- `crypto_btc_steps3.json`: the ticker lookup resolves "Bitcoin" to BTCUSD,
  but the model reports plain `BTC` misresolving to the Grayscale Bitcoin
  Mini Trust ETF. Crypto quotes through finance_search would risk quoting
  the wrong instrument; the rail answers crypto from Argus's own Kraken-backed
  data instead.
- `fx_eurusd_steps3.json`: `EURUSD=X` returns an empty quote payload and the
  ticker lookup returns NOT_FOUND. FX is genuinely uncovered; same honest
  degradation path.
- `peers_netflix_steps3.json`: peers arrive as model knowledge verified
  through `tickers_lookup` batches plus a `profile` grounding for the anchor.
- `etf_spy_constituents_steps3.json`: the `etf_holdings` result category
  works fully (504 holdings with weights, top weights first). This category
  is what the etf_constituents shape parses into resolver-verified peers.
- `background_thorough_nflx_dis.json`: background mode lifecycle observed
  queued -> in_progress -> completed in 21.8s for a 10-step comparison;
  submit returned in 0.22s.

## Flag-off byte identity (`flag-off-checksum/`)

Cross-commit proof at full precision, not an assertion.
`scripts/qa/research_rail_flag_off_checksum.py` drives three deterministic
chat turns through the real `/chat/stream` surface with
`ARGUS_RESEARCH_RAIL_ENABLED` off and a deterministic injected interpreter,
then hashes the canonicalized stream frames, persisted transcript, and usage
payloads (volatile identifiers and timestamps canonicalized, all else exact).

- `baseline.json`: run at a clean checkout of `01044cda` (the integration
  tip this branch merged forward onto), with the imported module path
  verified to be the clean checkout's own `src/argus`.
- `head.json`: run at the lane head after the section 11b absorption.

Both produce digest
`55bb1b89ce5493c5e4f5c2374b5e043b24eb792e499676344c64f9dcef91b8b7`. The
digests are identical: flag off, the chat surface is byte-identical to
integration.

## Browser evidence (`browser/`)

Regenerated 2026-08-09 at the post-absorption head against live providers,
in dev memory mode at the **default** turn-call allowance (no knob raised).
Every journey is organic typed input or a starter-chip tap; **no
server-seeded cards anywhere**. Next to every PNG sits a `.txt` dump of the
same page's rendered text, captured in the same instant; every frame's text
was read before it was trusted, and the one transient error card the session
produced (an interpreter-level rejection, upstream of the rail) was caught by
that reading and re-captured clean.

Frames (`-en` and `-es` variants unless noted):

- `00-flag-off-empty-chat-en`: the rail flag off. Integration's shipped
  entry surface: wordmark heading, legacy placeholder and test chips, no
  greeting, no rail copy.
- `01-empty-chat`, `11-empty-chat-mobile`: signed-in empty chat at 1280px
  and 375px. Muted mark, time-of-day greeting, the three range-spanning
  chips (scroll row at mobile width), locked composer placeholder, legal
  disclosure, suggestions toggle.
- `02-chip1-company-lookup`: chip 1 tapped organically. Balanced-shape
  grounded answer (Netflix business model with segment figures and sources)
  ending in a runnable row.
- `03-chip2-comparison-thorough`: chip 2 tapped organically — the exact
  question section 11b names as broken. It now reaches the rail's thorough
  shape: market-snapshot and business-scale tables, an honest "not shown
  rather than estimated" caveat for a missing figure, and a versus row
  naming all three resolver-verified identities.
- `04-confirmation-from-research`, `05-peer-added-undo-toast`,
  `06-peer-undo-restored`: the organic peer flow. An ETF-holdings research
  turn offers its anchor row; the tapped confirmation offers the remaining
  verified holdings as Add rows on the Try-next surface; one tap adds the
  peer with no turn spent (chip motion, single calm Undo toast); Undo
  restores the previous set exactly and the peer becomes offerable again.
- `07-chip3-test-confirmation`: chip 3 tapped organically; the builder asks
  the one missing amount question. The test shape reaches the builder, not
  a capability menu.
- `08-discovery-find`: "Find me cybersecurity stocks" runs the rail's find
  operation. Resolver-verified candidate rows with reasons, the honest
  "from general knowledge, not a current search" marker, and the
  "Search for current results" escalation row: the discovery experience,
  unchanged.
- `09-crypto-honest`: crypto quoted from Argus's own market data with the
  coverage note and a runnable row; never fabricated through finance_search.
- `10-etf-constituents`, `12-table-mobile`: the section 2 ETF ability.
  Top-holdings tables with weights (SPY 504 positions; QQQ concentration
  figures), holdings parsed into resolver-verified rows, including a versus
  row against the top constituents; the table scrolls inside its own
  container at 375px.

Two hosted-behavior notes recorded honestly: dev memory mode runs thorough
research synchronously (production takes the background job path; the job
lifecycle is covered by tests and the committed background probe), and the
interpreter's known intermittent validator rejection can still fail a turn
upstream of the rail; the evidence session hit it twice and both retries
succeeded with identical input.

## The five shapes (`browser/20-` through `browser/24-`)

Captured 2026-08-09 at the shapes head against live providers, default
configuration, organic typed questions, both languages. Every frame's text
dump was read before the frame was kept; three defects were caught that way
and fixed before this set was recorded (market pulse and sector radar
dead-ending on "nothing to test" while naming tradable assets, and ticker
badges concatenating in copied text).

- `20-market-pulse`: "What are the biggest movers today?" Real gainers,
  losers, and most active with figures, volumes, and the session as-of, plus
  index levels. Rows offer the movers the answer itself named.
- `21-screening`: "Show me semiconductor stocks under a 20 P/E". The answer
  carries a condition-by-condition table (semiconductor condition, P/E
  condition) with the figure proving each, states it is not an exhaustive
  world screen, and explains that negative P/E names were excluded rather
  than silently dropped.
- `22-sector-radar`: "What's happening in cybersecurity stocks?" Sector
  analysis: ETF performance year to date, what is driving the move, leaders
  against laggards, and a live scoreboard. Not a list of company
  descriptions.
- `23-comparison-p1`: "Compare PLTR to LMT". The P1 defect, fixed: a grounded
  financial comparison with a runnable versus row, where this exact input
  previously answered "What date window should I use for PLTR?".
- `24-single-stock`: "How is Netflix doing?" Grounded single-stock analysis
  ending on a runnable row.

Each shape reaches the rail from an organic question in both languages,
grounds through finance_search, ends on a resolver-verified runnable row,
records `screening` (surveys) or its shape's class, and caches under the
section 7 data class for its data.
