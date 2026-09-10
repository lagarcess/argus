# Declared DCA card browser verification

Candidate: `72aa04a06d00a76421414e778d67fc2cf3ccd0f2`. Checkout was clean before and after; candidate did not change.

The existing two declared-backtest cases in `web/e2e/tool-registry.spec.ts` passed (2.4s). The browser intercepted the API with committed fixtures; there were no live API, model/provider, or real backtest calls. This is UI rendering evidence, not provider or financial-engine acceptance.

Both en and es-419 card images were inspected. The full answer, return-on-contributions label, zero starting principal, $200 monthly contribution, 10 bps fee, 5 bps slippage, SPY benchmark and chart are visible. No card content is hidden by the chat header. Viewport changed from 1280x900 to 1280x1500, with actual transcript scroll only. Card top:104; bottom:1125.5. No DOM, styling, card data, source, fixture, configuration or Git state was altered.

Image dimensions: tool-backtest-en.png 273x1022, tool-backtest-es-419.png 317x1022.

`command.txt` contains the exact command; `browser.log` contains the test log; `scroll-captures.jsonl` contains viewport and scroll observations; `provenance.json` records SHA, fixture hash, image dimensions/hashes, result and cleanup. The owned test server on port3192 is stopped.

These temporary artifacts remain outside the checkout during the paid measurement freeze. They can be copied into durable evidence after the root agent authorizes that step.
