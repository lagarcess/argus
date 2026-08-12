# Research citation, synthesis, and source-selection browser proof

Captured on 2026-08-12 from the full local Argus web and API stack with the
configured live research path. The four journeys exercise both supported
languages and both production question shapes from issues #451, #457, and
#407.

## Acceptance matrix

| Journey | Question | Result | Source-drawer proof |
| --- | --- | --- | --- |
| English fundamentals | `What were Apple's main growth drivers?` | Argus synthesized the drivers and rendered five public sources. | Five distinct publishers; no provider-owned host. |
| Spanish fundamentals | `¿Cuáles fueron los principales impulsores del crecimiento de Apple?` | Argus synthesized the drivers in Spanish and rendered five public sources. | Five distinct publishers; no provider-owned host. |
| English market movers | `What are today's biggest market movers?` | Retrieval returned five current sources but no resolver-verified mover. Argus rendered only `I found sources, but could not extract today's market movers from them.` and emitted no subject rows. | Five distinct publishers, all dated 2026-08-12. |
| Spanish market movers | `¿Cuáles son los mayores movimientos del mercado de hoy?` | Argus named current movers, including EROC, HRB, CRWV, and NBIS, and emitted rows only for tickers named in the answer. | Five distinct publishers, all dated 2026-08-12. |

The English movers result is an accepted, explicit synthesis-recovery outcome.
It demonstrates that successful retrieval cannot produce generic figure or
asset disclaimers when no typed subject exists. The Spanish result demonstrates
the successful synthesis branch of the same contract.

## Assertions exercised by the browser harness

- Narrative fundamentals responses must persist and render at least one public
  source.
- The rendered drawer count must equal the persisted typed-source count and
  must never exceed five.
- Provider-owned hosts are rejected.
- At most one selected page may come from each publisher.
- An explicitly dated source for a `today` market-pulse question must be dated
  on or after the question's period start, 2026-08-12 in these journeys.
- A movers response must either name every emitted typed subject or render the
  precise synthesis-recovery sentence with zero subject rows.

## Artifacts

- `browser/01-fundamentals-en-answer.png`
- `browser/01-fundamentals-en-sources.png`
- `browser/02-fundamentals-es-answer.png`
- `browser/02-fundamentals-es-sources.png`
- `browser/03-movers-en-answer.png`
- `browser/03-movers-en-sources.png`
- `browser/04-movers-es-answer.png`
- `browser/04-movers-es-sources.png`

The PR terminal audit records the exact candidate head used for final
revalidation.
