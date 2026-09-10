# Registry declaration: rendered fixture acceptance

Source: `b17d25775028b7d7e2ea2f30ab35348291c973cc`. The original 14 registry browser cases plus two authored MACD controls passed **16/16 in 54.7s** in English and `es-419`, at desktop and mobile widths. All selected images come from this final run using the corrected authored fixtures.

This is **fixture-only browser evidence**. The test-only echo declaration and real registered backtest projector/presenter produced the card contracts. DCA/MACD metrics and chart data were authored test inputs. All browser API replies, recompute responses and job transitions were intercepted fixtures; progress used an authored fetch stream. No interpreter, provider, backtest handler or real API ran. Spend: **$0**. These results demonstrate rendering and frontend continuity, not live answers, backend recompute or numerical engine correctness.

| Surface | English | Spanish |
| --- | --- | --- |
| Editable card, desktop | [Image](screenshots/tool-card-en-1280.png) | [Image](screenshots/tool-card-es-419-1280.png) |
| Editable card, mobile | [Image](screenshots/tool-card-en-390.png) | [Image](screenshots/tool-card-es-419-390.png) |
| DCA facts and costs | [Image](screenshots/tool-backtest-en.png) | [Image](screenshots/tool-backtest-es-419.png) |
| MACD windows and costs | [Image](screenshots/signal-card-en.png) | [Image](screenshots/signal-card-es-419.png) |
| Repeated calls after reload | [Image](screenshots/tool-jobs-en.png) | [Image](screenshots/tool-jobs-es-419.png) |
| Historical card is read-only | [Image](screenshots/tool-history-en.png) | [Image](screenshots/tool-history-es-419.png) |
| Declared progress | [Image](screenshots/tool-progress-en.png) | [Image](screenshots/tool-progress-es-419.png) |

Assertions cover known zero versus the blank unknown, two edits/revision advances, withholding an invalid edit, reload and sibling preservation, latest-message edit eligibility, debounce cancellation on send, and asynchronous calls completing out of order. DCA retains monthly cadence, $200 contributions, zero seed, and 10/5 bps modeled fee/slippage. The additional authored signal controls retain the MACD 12/26/9 windows, chart and modeled costs before and after reload. These expectations derive from the canonical fixture inputs. The echo tool's `known`/`other`/`unknown` identifiers and incidental authored user text are not product localization claims.

The [numeric ledger](fixture-coherence.json) binds principal, net return, profit, ending value and chart endpoints. MACD uses the engine's $10,000 starting capital: +18.4% produces $1,840 profit and $11,840 ending value. DCA uses `DcaCapitalPlan.total_invested(3)`: $600 contributed produces $110.40 profit and $710.40 ending value, displayed as $710 by the existing card's whole-dollar formatting. DCA's chart starts with the first $200 buy, then includes the two later monthly contributions. Both illustrative weekday charts start/end on the snapshot's January 2–March 1 window. The authored monotonic paths carry 0% drawdown; they are not engine output.

The final run observed 208 mocked API requests and **zero external requests, unhandled API requests and page errors**. Service workers were blocked; HTTP/WebSocket requests outside loopback were denied, and an unmatched API route would abort and fail the case. Fixture generation blocked socket connections and DNS before imports and recorded zero attempts. See [per-case network logs](coherent-network) and the retained [guard](harness/registry-evidence-hooks.ts).

All 14 selected images were visually inspected. Initial locator captures overlapped sticky chrome, so the retained [capture helper](scroll-capture.cjs) uses real transcript scrolling; it never changes styles or hides chrome. Behavioral widths remain 1280/390 pixels. Generic-card captures retain their 900-pixel height. DCA and repeated-call captures increase height from 900 to 1500; signal captures increase height from 1000 to 1500. History captures decrease height from 1000 to 900; progress stays at 1000. Taller images show complete cards and do not claim a 900/1000-pixel viewport fits them. [Per-image geometry](scroll-captures.jsonl) records original/final viewports and actual scroll positions.

**Superseded evidence:** visual review found the shared test inputs independently hard-coded profit $120 and return +18.4%, making the original DCA/MACD cards inconsistent. Only the temporary generator was corrected; production and shared test factories were unchanged. Earlier [16-case results](full-matrix-results.json), [10-case recapture results](capture-results.json), logs and network records are retained as historical execution records, not acceptance of those fixtures. Their affected [fixtures, generator, provenance and four images](superseded) are explicitly superseded. The final run above repeated the same 16 cases with coherent values and the disclosed capture helper.

Production web code came from an isolated `git archive` of the exact SHA. The original test bodies were unchanged; two evidence-hook statements and the two authored signal controls exist only in the archive. The unchanged generator's relative `docs/reports/evidence/registry` output landed inside that archive, then selected files were copied here. No production source or test files changed during capture. Playwright stopped its browser/server; port 3195 had no listener afterward. The scratch archive and initial captures were preserved.

[Manifest](browser-manifest.json), [fixture/source provenance](provenance.json), [final results](coherent-matrix-results.json), [commands](command.txt) and [offline validation](verify-bundle.py) retain the evidence boundary. Final CI, review and promotion remain the release captain's responsibility.
