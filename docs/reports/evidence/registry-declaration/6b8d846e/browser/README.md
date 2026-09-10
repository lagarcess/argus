# Registry declaration: post-merge browser acceptance

Source: `6b8d846e8543d532ecbfac73b9d744a3b1ac1ec2`, after merging integration `3ceada309a450c12335ad6e1048ab141ce1680bb`. PR #581 changed the shared `ChatInterface` owner, so the same corrected registry fixture matrix was rerun on a fresh archive. **16/16 cases passed in 57.4s**, with no skipped, failed or flaky cases. All **14 new screenshots** were visually inspected.

Scope remains fixture-only rendering: the original 14 cases plus the same two authored MACD controls, English and `es-419`, desktop/mobile widths. There were **208 intercepted API requests, zero external requests, zero unhandled API requests and zero page errors**. No real API, interpreter, provider or backtest handler ran. Spend: **$0**. This demonstrates frontend rendering and continuity with authored replies, not live answers, backend recompute or numerical engine correctness.

| Surface | English | Spanish |
| --- | --- | --- |
| Editable card, desktop | [Image](screenshots/tool-card-en-1280.png) | [Image](screenshots/tool-card-es-419-1280.png) |
| Editable card, mobile | [Image](screenshots/tool-card-en-390.png) | [Image](screenshots/tool-card-es-419-390.png) |
| DCA facts and costs | [Image](screenshots/tool-backtest-en.png) | [Image](screenshots/tool-backtest-es-419.png) |
| MACD windows and costs | [Image](screenshots/signal-card-en.png) | [Image](screenshots/signal-card-es-419.png) |
| Repeated calls after reload | [Image](screenshots/tool-jobs-en.png) | [Image](screenshots/tool-jobs-es-419.png) |
| Historical card is read-only | [Image](screenshots/tool-history-en.png) | [Image](screenshots/tool-history-es-419.png) |
| Declared progress | [Image](screenshots/tool-progress-en.png) | [Image](screenshots/tool-progress-es-419.png) |

Assertions retain known zero versus the blank unknown; two edits/revision advances; withholding invalid edits; reload and sibling preservation; latest-message eligibility; debounce cancellation on send; and asynchronous calls completing out of order. DCA retains monthly $200 contributions, zero seed and modeled 10/5 bps fee/slippage. The signal controls retain MACD 12/26/9 windows, chart and costs before and after reload. `known`/`other`/`unknown` are declared test-only identifiers.

The [numeric ledger](fixture-coherence.json) binds authored values to the real capital owner and presenter. DCA has $600 contributed, +18.4%, $110.40 profit and $710.40 ending value, displayed as $710 by existing whole-dollar formatting. MACD has $10,000 principal, $1,840 profit and $11,840 ending value at the same return. Both chart endpoints use the snapshot's January 2–March 1 dates. DCA's chart begins with the first $200 buy and adds later monthly contributions. Illustrative monotonic paths carry 0% drawdown. All five generated fixture/ledger hashes match the corrected [b17 bundle](../../b17d2577/browser/README.md); its superseded history remains there, untouched.

The exact [capture helper](scroll-capture.cjs) uses real transcript scrolling and viewport resizing, with no style changes or hidden chrome. Widths remain 1280/390 pixels. Generic-card capture height stays 900; DCA/repeated-call heights change from 900 to 1500; signal heights change from 1000 to 1500; history changes from 1000 to 900; progress stays 1000. These taller images show complete cards, not a claim that they fit shorter viewports. [Geometry records](scroll-captures.jsonl) retain original/final viewports and actual scroll positions.

Fixture generation blocked socket connections and DNS before imports, with zero attempts. The browser [guard](harness/registry-evidence-hooks.ts) blocks external HTTP/WebSocket requests and unmatched APIs; service workers are disabled. Progress uses an authored fetch stream. The real declaration/presenter consumes authored input; intercepted replies own API/recompute/job behavior. No production/test source changes or dependency installation occurred. Archive verification found only the documented evidence-hook prefix in the original spec, plus authored temporary controls. Browser/server exited, and port 3196 had no listener afterward.

[Manifest](browser-manifest.json), [source provenance](provenance.json), [results](coherent-matrix-results.json), [network records](network), [commands](command.txt) and [offline verification](verify-bundle.py) bind this evidence to the merge head.
