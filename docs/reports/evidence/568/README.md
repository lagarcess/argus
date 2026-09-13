# A withheld answer keeps where Argus looked (PR #568)

Browser evidence for the user-visible half of PR #568, captured at code head
`c5214b57` on 2026-09-09 in both languages at desktop (1280) and mobile
(390) widths. No provider, model, or hosted database was touched: the page
hydrates a persisted conversation, the same path a reload takes in
production.

## What the turn is

The recorded Banco Popular probe from the retrieval-parameters lane
(`docs/reports/evidence/545/probes/domain_filtered_local_source.json`: a
Spanish question, `user_location` DO, the web search restricted to
`popularenlinea.com`, eleven pages retrieved, no rate on any of them),
composed through the rail's own seam (`_packet_from_response`, then
`_packet_stage_result`) once per language by `browser/replay_api.py`, and
seeded into a memory-mode backend as a user question plus the assistant
turn it produces. Nothing in the assistant turn is hand-written: the note,
the degraded code, and the sources are what the composition emits.

## What the user saw before, replayed

The same three withheld recordings replayed through the composition seam at
integration `76f5947b`, before this PR:

| Recording | Code | Pages retrieved | Pages in the drawer | The page shown, under "Sources used to inform this answer" |
| --- | --- | ---: | ---: | --- |
| `domain_filtered_local_source` | `research_figures_unverified` | 11 | 1 | popularenlinea.com, "Préstamo Emprendimiento Popular" |
| `domain_filtered_rate_publishers_no_recency` | `research_figures_unverified` | 23 | 2 | bancentral.gov.do home; sb.gob.do financial statements |
| `market_pulse_vaguest` | `survey_synthesis_incomplete` | 37 | 1 | finance.yahoo.com, "Stock Splits Calendar" |

The sources were already carried on both composition paths. The dead end
was the framing: a drawer titled "Sources Argus read" with the note
"Sources used to inform this answer" ("Fuentes usadas para fundamentar esta
respuesta") on a turn that informed nothing, and a button that counted them
as sources.

## What the user sees now

| File | Language | Width | Shows |
| --- | --- | --- | --- |
| `browser/withheld-turn-desktop-en.png` | en | 1280 | the withheld note and the "Where Argus looked ›" button |
| `browser/where-argus-looked-desktop-en.png` | en | 1280 | the drawer: "Where Argus looked", its note, the bank's page with its real title, domain and date |
| `browser/withheld-turn-mobile-en.png` | en | 390 | the same turn on a phone |
| `browser/where-argus-looked-mobile-en.png` | en | 390 | the bottom sheet with the same framing |
| `browser/withheld-turn-desktop-es-419.png` | es-419 | 1280 | "Encontré fuentes, pero no pude verificar…" and "Dónde buscó Argus ›" |
| `browser/where-argus-looked-desktop-es-419.png` | es-419 | 1280 | "Dónde buscó Argus" and its note |
| `browser/withheld-turn-mobile-es-419.png` | es-419 | 390 | the same turn on a phone |
| `browser/where-argus-looked-mobile-es-419.png` | es-419 | 390 | the bottom sheet |

The driver's own read of the rendered page, per capture: button text
"Where Argus looked ›" / "Dónde buscó Argus ›"; the drawer title present;
the bank's page listed with its title "Préstamo Emprendimiento Popular |
Banco Popular Dominicano" and domain `popularenlinea.com`; the old
"Sources Argus read" / "Fuentes que Argus consultó" title absent; zero page
errors, in all four captures.

Selection is unchanged: eleven pages on one publisher collapse to that
publisher's first page, the way a published answer's drawer already works.
The page is a loan product and its title says so; the framing above it says
Argus read it and could not verify the answer with it. That is the honest
statement, and the reader can open the bank's own site from it.

## Reproduce

```bash
# backend, memory mode, seeded from the recording, no keys
PR568_QA_TREE="$PWD" PR568_QA_IDS_FILE=/tmp/pr568_ids.json \
  poetry run python docs/reports/evidence/568/browser/replay_api.py
# web, in a second shell
cd web && NEXT_PUBLIC_ARGUS_API_URL=http://127.0.0.1:8568/api/v1 \
  NEXT_PUBLIC_MOCK_AUTH=true NEXT_PUBLIC_ENABLE_SPANISH=true \
  NEXT_PUBLIC_RESEARCH_RAIL_ENABLED=true bun run dev -- --port 3568
# capture, in a third
PR568_QA_TREE="$PWD" PR568_QA_IDS_FILE=/tmp/pr568_ids.json \
  node docs/reports/evidence/568/browser/drive.mjs
```

The driver sets the profile language through `PATCH /api/v1/me` before each
language's captures; the UI follows the profile, not the browser.
