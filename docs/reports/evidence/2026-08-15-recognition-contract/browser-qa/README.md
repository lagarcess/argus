# Browser QA, recognition-contract lane (frontend behavior)

Hand-driven in the in-app browser against the lane worktree at `afd07cd0`:
backend `fastapi dev` with the canonical env sourced read-only plus runtime
overrides (live providers, mock auth, memory persistence, workflow dispatch
off), frontend `bun run dev` with `NEXT_PUBLIC_MOCK_AUTH=true` and
`NEXT_PUBLIC_ENABLE_SPANISH=true` injected as process env; neither `.env`
file was written. Evidence per turn is the DOM text extract (the pane's
paint-throttling makes DOM extraction the reliable proof), one file per
scenario beside this README.

## Verdicts

| scenario | on-screen result |
|---|---|
| "remove AAPL" | PASS: card → MSFT+NVDA, re-run fired, result prose names only MSFT+NVDA (+96.1% vs SPY) |
| "add TSLA" | PASS: all four on the card, none dropped |
| "remove AAPL and replace with TSLA and GOOGL" | PASS: MSFT, NVDA, TSLA, GOOGL |
| "remove AAPL and change the start to April 1 2026" | see finding 1: date conflicted with the 2024 card, honest clarify, then the removal was lost across the detour; single-turn valid variant (`e4b`) lands both |
| Spanish messy 4-op compound | PASS with one extra turn: guard refused the model's whole-set misread (no wrong card), clarify → all four ops land (MSFT/NVDA/TSLA/GOOGL, $8,000, QQQ) |
| DCA ceiling "I only have $5,000... every month" | 0/3 ceiling-recovery in this window (per-month reading rendered instead, coherently); never silently runs — approval always required; both full eval runs passed the ceiling mode same day |
| DCA "$5,000 to start and $0 each month" | PASS in one turn: renders as Buy and Hold with the $5,000 seed |
| weekly options ×5 | 5/5 limit named + AAPL kept + runnable offered (once with three alternative chips); 4/5 window echoed — above the expected ~2/5 |

## Findings (payload right, screen wrong)

1. **Cross-turn compound drop (the real catch).** "remove AAPL and change the
   start to April 1 2026" on a 2024 card: turn 1 correctly refuses all-or-nothing
   and asks about the date conflict; after the user answers with a valid window,
   the new card carries the date but **AAPL is back** — the parked removal never
   re-applies and nothing discloses the loss. Single-turn compounds are proven
   (eval, matrix, `e4b`); the drop lives in clarification-continuity state, a
   surface outside this lane's eleven evidence cases. Repro in `e4-remove-plus-date.txt`.
2. **Recovery prose follows the persisted UI language, not the message
   language, in both directions.** English fallback prose on a Spanish turn
   (E5) and Spanish recovery prose on English turns (all five weekly-options
   attempts). Cards, chrome, and chips localize correctly; it is the
   fallback/recovery voice that misses the message language.
3. **Duplicate option label in a voiced list.** The future-window recovery
   offered "Test it over a historical period" twice in one sentence
   (`e4-remove-plus-date.txt`, turn 2).
4. Observation: the D1 ceiling sentence is genuinely ambiguous in English and
   this serving window resolved it per-month 3/3; the card renders that
   reading faithfully and never runs without approval.
