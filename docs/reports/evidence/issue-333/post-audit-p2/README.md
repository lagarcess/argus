# Issue #333 post-audit P2 evidence

Browser artifacts were captured from behavior commit
`186b9723705c71efe03201e56961a0e7d7f3c6c4` on 2026-08-03.

## Bilingual localized rejection

The browser loaded a durable confirmation, clicked its Run action once, and
received a typed `422 kraken_ohlc_window_exceeded` response. Each check asserted
that exactly one action request fired, the localized recovery was visible, and
the raw provider detail was absent.

- [English rejection](./localized-window-rejection-en.png)
- [Latin American Spanish rejection](./localized-window-rejection-es-419.png)

Command:

```bash
ARGUS_EVIDENCE_DIR="$PWD/../docs/reports/evidence/issue-333/post-audit-p2" \
  bunx playwright test e2e/chat-action-recovery.spec.ts \
  --grep "Retest window rejection is localized" \
  --project=chromium --workers=1
```

Result: `2 passed`.

## Focused hermetic verification

```bash
OPENROUTER_API_KEY= ALPACA_API_KEY= ALPACA_SECRET_KEY= \
ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture \
  poetry run pytest tests/test_retest_setup.py tests/test_retest_action.py \
  -q --no-cov
```

Result: `58 passed`.

```bash
bun test __tests__/chat-recovery-display.test.ts __tests__/locales.test.ts
```

Result: `32 passed`.

The previously accepted live evaluation remains `40/40`; this post-audit pass
did not rerun or spend that suite.
