# Rowless research browser acceptance

Head: `c6c28fefe5b30c1f5d0a67656dc9c6fa025a44e2`; repository clean before and after.

Two authored rendered-fixture cases passed: English and Spanish (es-419), initial chat hydration and reload. This is not a real API result or live research-answer claim. There were no provider, backtest, dispatcher, recompute, or public-receipt calls.

The fixture passed through the registered `balanced_lookup` declaration's `CitedResearchFiguresResult` validation and `result_card` presenter, without invoking its callable. Each completed result contains an authored nonblank narrative, two retained public-format source references, and zero numeric rows. The card's numeric answer is null. The current chat UI rendered those facts and sources before and after reload.

Both full-page screenshots were visually inspected. Narrative and source contents are fully readable, the chrome is localized, and no numeric-answer block appears. Source links were inspected but not followed.

`provenance.json` binds the fixture and source hashes. `results.json` records the two passes, network counts, screenshot inspection, clean-head check, and server shutdown. `network-en.json` and `network-es-419.json` record every intercepted application request and both rendered phases. All API reads were fulfilled by the authored transcript or the unchanged `mobile-shell-fixture`; the external-network deny route recorded zero attempted external requests. Playwright's `webServer` owned the loopback server and stopped it after completion; port 3193 has no listener.

`browser-approved.log` and `playwright-results.json` contain the successful run. `browser.log` preserves the initial sandbox-only EPERM listener failure. The same two cases ran after bounded loopback/browser permission was approved. All generated files remain in this temporary directory; the repository was not edited.

The capture artifacts are now retained in this directory. The temporary served checkout and dependency symlink are excluded.
