# Empty chat polish evidence

Lane: `claude/empty-chat-polish-6330b8`, off `codex/private-alpha-next`. Spec:
`docs/specs/argus-active-roadmap.md`, section "Empty chat polish". Closes #403.

Captured 2026-08-09 against a real backend, not a fixture. Twelve frames, both
languages, mobile 390 and desktop 1280. Every frame carries its rendered text
alongside the image, because the text is what proves the sentence and the image
is what proves the layout absorbed it.

## Setup

Backend on port 8010 from this worktree with `ARGUS_MOCK_AUTH=true`,
`ARGUS_PERSISTENCE_MODE=memory`, and **`ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider`**
with the real Alpaca credentials. The provider mode matters: the hermetic
`synthetic_unit_fixture` mode reports no session at all by design, so a fixture
run could not have produced the closure frames.

Frontend on port 3010 with `NEXT_PUBLIC_RESEARCH_RAIL_ENABLED=true`, since the
signed-in greeting surface is behind that flag. No `.env` or `web/.env.local`
file was written.

Playwright drove the capture. Language is set through `PATCH /me`, the way the
settings picker sets it, because language is a profile preference and the
browser store is only a pre-auth hint. The local clock is shifted by a wall-clock
shim on `Date` so the time-of-day slot can be reached without waiting for it;
timers stay real, so the typewriter still runs and each frame is captured only
after the caret clears.

## Live market session

2026-08-09 was a Sunday. The endpoint answered from the real Alpaca trading
calendar:

```json
{
  "session": {
    "phase": "closed_weekend",
    "is_market_day": false,
    "as_of": "2026-08-09T17:43:05.824047-04:00"
  }
}
```

The `-04:00` offset is Eastern daylight time, resolved server side. The frontend
never computes it.

## Frames (`browser/`)

Console errors: **zero on all twelve**. `report.json` and `settings-report.json`
carry the machine-readable assertions behind the table.

| Frame | Language | Viewport | Local time | Name | Greeting |
| --- | --- | --- | --- | --- | --- |
| `01-empty-chat-en-desktop` | en | 1280x900 | 12:00 | none | What is worth a look today? |
| `02-empty-chat-en-mobile` | en | 390x844 | 12:00 | none | What is worth a look today? |
| `03-empty-chat-es-desktop` | es-419 | 1280x900 | 12:00 | none | ¿Qué vale la pena revisar hoy? |
| `04-empty-chat-es-mobile` | es-419 | 390x844 | 12:00 | none | ¿Qué vale la pena revisar hoy? |
| `05-closed-market-en-desktop` | en | 1280x900 | 19:00 | none | Stocks are closed for the weekend. Crypto never stops, so there is still plenty to test. |
| `06-closed-market-es-mobile` | es-419 | 390x844 | 19:00 | none | La bolsa está cerrada por el fin de semana. Las criptos no paran, así que hay mucho por probar. |
| `07-named-en-desktop` | en | 1280x900 | 23:30 | Lucas | Still up, Lucas. What are you curious about? |
| `08-named-es-mobile` | es-419 | 390x844 | 23:30 | Lucas | Todavía por aquí, Lucas. ¿Qué te da curiosidad? |
| `09-settings-field-en-desktop` | en | 1280x900 | live | unset then Lucas | settings field |
| `10-settings-field-en-mobile` | en | 390x844 | live | unset then Lucas | settings field |
| `11-settings-field-es-desktop` | es-419 | 1280x900 | live | unset then Lucas | settings field |
| `12-settings-field-es-mobile` | es-419 | 390x844 | live | unset then Lucas | settings field |

The four settings frames come in pairs: the base frame shows the field unset,
and `-saved` shows it after typing a name and pressing Enter, with the value
read back from `GET /me` to prove it persisted rather than only rendered.

### What each set proves

**No toggle anywhere.** Every one of the twelve rendered-text files was checked
for "Show suggestions", "Hide suggestions", "Mostrar sugerencias", and "Ocultar
sugerencias". None appears. The suggestion chips render in all twelve without a
control gating them, which is the point: they stop when the empty chat stops.
Compare `docs/reports/evidence/377/browser/01-empty-chat-en.txt`, which still
carries "Hide suggestions" on line 17.

**The greeting is not one sentence per slot.** Frames 01 and 05 are the same
day, the same language, and the same viewport, and differ only in the local
hour. They produce different lines, because the day-stable pick is per pool and
the pool widens when a session is active.

**Closure is true for every asset class.** Both closure frames name stocks and
crypto in the same sentence. A bare "markets are closed" would be false for the
crypto and currency-pair users Argus supports.

**The long sentence survives 390.** `06-closed-market-es-mobile.png` is the
worst case: the longest string in the pool, in the longer language, at the
narrowest width. It wraps to four balanced lines with no overflow, the chips
still scroll above the composer, and the disclaimer still sits at the bottom.

**The name appears only where it was written in.** Frames 07 and 08 carry
"Lucas". Frames 01 through 06 have a profile with no name and use none.

**`preferred_name` is not `display_name`.** The settings frames show both at
once: "Mock Developer" in the identity block, "What should Argus call you?" as
its own labelled field below a rule, reading "Not set" or "Sin definir" until
the user fills it.

### A note on the duplicated greeting line

Every empty-chat text capture shows the greeting twice. That is expected and
documented in `web/__tests__/empty-chat-greeting-aria.test.ts`: `innerText`
includes both the `aria-hidden` typewriter paragraph and the `sr-only` polite
status region. The accessibility tree contains the sentence once.
