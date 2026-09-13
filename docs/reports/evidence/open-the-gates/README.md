# Open the gates: evidence

The founder's lane of 2026-09-10 deletes three rules and fixes the money:
the withholding PR #562 added at the composition seam, the four-turn sharing
cap, the fast-shape sharing exclusion, and a rate table that rejected every
real invoice. This folder holds the reproduction, the side-by-side transcripts
the acceptance asks for, the browser drive of the share flow, the probes that
decided the two configuration questions, and the live eval case. Every provider
call went through the repository's own client, prompt builder and spec.

Runs were driven against a local Argus API in memory persistence with mock
auth, the real interpreter and the real research provider, and the live asset
provider so any ticker resolves (`drivers/serve.py`). Perplexity was asked the
same question as typed, through the Agent API with its finance and web tools
and none of Argus's instructions or schema (`drivers/perplexity_plain.py`).
`perplexity.ai` was also opened signed out in a browser for the Nike question
and answered $37.35, down $0.75 (1.97%), citing Yahoo Finance.

## The reproduction

`before/argus-nike.json` is "what's the price of nike today" at integration
head `ba5a9fb7`, before any change. **The founder's refusal did not reproduce
on this run.** Argus answered "Nike (NKE) is priced at **$37.35 per share**, as
of September 9, 2026", because the model cited the provider's own finance page
as the row's source, which the provider-host scrub nulls and the citation check
kept. Three further probes of the same question at the same head
(`probes/nike-fast-1.json`, `nike-fast-2.json`, `nike-fast-web.json`) did the
same. The rejection fires when the model cites an outside page instead, as it
did on the founder's recorded turn; on the fast shape that is the less common
outcome, and the deterministic replay of it is
`tests/research/test_published_answers.py::test_a_row_citing_a_page_outside_the_retrieval_record_publishes`.

What did reproduce, every time: the invoice was rejected as `rate_mismatch`
(`before/api-log-excerpt.txt`: expected $0.00041 for 81 uncached input tokens,
$0.00032 billed), the sidecar's `cost_usd` was null, the fallback recorder
failed, and the share candidate was refused for `unsupported_shape`.

## Side by side, after the change

Argus at the lane head; Perplexity as typed. Costs are provider-reported.

| Question | Argus | Perplexity |
| --- | --- | --- |
| what's the price of nike today | "$37.35 per share, as of September 9, 2026. The market was in after-hours trading when the quote was retrieved." Fast shape, 1 typed row, 20.4s turn, $0.048 recorded on the sidecar. `after/argus-nike.json` | "$37.35 USD, down $0.75 (1.97%). The market is currently in after-hours trading." 9.8s, $0.047. `perplexity-nike.json` |
| ¿A cuánto está la acción de Apple hoy y cuánto subió esta semana? | "US$315.34, con datos al 9 de septiembre de 2026. La variación acumulada de esta semana no pudo recuperarse." Fast shape, 1 row, 29.5s, $0.052. `after/argus-apple-es.json` | "US$315,34 ... bajó 1,447% esta semana" against Friday's close, with a ycharts page. 19.8s, $0.087. `perplexity-apple-es.json` |
| what is apple's p/e ratio right now? | "36.12×, as of September 9, 2026." Fast shape, 1 row, 27.1s, $0.049. `after/argus-apple-pe.json` | "P/E ratio is 36.12 as of the latest market close on September 9, 2026." 5.6s, $0.039. `perplexity-apple-pe.json` |
| how much did the S&P 500 move this week? | "down 82.24 points, or 1.1%, so far this week. SPY last traded at $762.40", plus a movers table the survey read added. Balanced shape, 12 rows, 53.9s, $0.161. `after/argus-spx-week.json` | "down 82.24 points, or 1.07%, this week through Wednesday's close" with a WSJ page. 19.4s, $0.094. `perplexity-spx-week.json` |
| why is NVIDIA stock moving this week? | Four themes and the $223.67 close, down 0.91% on the session. Balanced shape, 2 rows, 5 publisher sources, 30.1s, $0.112. `after/argus-nvda-week.json` | Down 2.90% for the week with six drivers. 21.7s, $0.088. `perplexity-nvda-week.json` |

Where Argus still says less than Perplexity, and why:

- **The Spanish weekly change.** The fast shape carries only the finance tool
  and a 30-second timeout. With four steps and finance only the model never
  fetches the history (`probes/apple-es-fast-4steps.json`); with web search
  offered it exceeds the timeout. Perplexity used two finance calls and a web
  search. This is the fast shape's retrieval configuration, not a rule, and it
  is left for the founder.
- **The S&P answer's drawer is empty** although its rows cite two pages: the
  survey freshness lower bound is the question date in UTC, and a question
  asked after 20:00 ET drops every same-day page. Pre-existing, filed in the
  lane report.

## The share flow

`browser/report.json` and the screenshots, 1280 and 390 CSS pixels.

- **Nike.** The header opens selection; the turn is listed and unselectable:
  "The sources cannot be shared. This answer has no supported publisher
  sources." (`nike-share-1280-en.png`, `nike-share-390-en.png`). The Spanish
  Apple quote reads the same in Spanish (`apple-es-share-*-es-419.png`). A
  fast quote's only source is the provider's own finance page, which the
  provider-host scrub keeps off every reader-facing surface, so after the
  fast-shape exclusion went the refusal moved from `unsupported_shape` to
  `missing_sources`. Sharing a provider-only quote needs either the typed rows
  as the receipt's evidence or retrieval that opens a public quote page; both
  are construction and the founder's call.
- **NVIDIA, end to end.** Select ("1 of 1 selected", no cap copy), preview
  (200), create (200), open the link in a fresh context with no cookies at
  both widths: 200, `noindex, nofollow, nocache`, the $223.67 close and the
  five publisher links on the page (`nvda-selected-1280-en.png`,
  `nvda-preview-1280-en.png`, `nvda-created-1280-en.png`,
  `nvda-public-1280-en.png`, `nvda-public-390-en.png`).
- **Six turns, no cap.** A conversation seeded with six copies of that
  eligible answer (`drivers/serve_seeded.py`): "0 of 6 selected", Select all,
  "6 of 6 selected", preview and create 200, the public page renders all six
  at phone width (`six-turns-*.png`, `browser/six-turns-report.json`).

## The two configuration probes

- **The fast shape's step budget was a refusal.** With the ticker not
  pre-resolved, two steps spend the only call on the ticker lookup and the
  answer is "Nike's current share price could not be retrieved"
  (`probes/nike-unresolved-fast-2steps.json`); four steps look it up and quote
  it, 10.5s, $0.052 (`probes/nike-unresolved-fast-4steps.json`). The budget is
  now four and `docs/reports/evidence/545/probes/fast_quote_typed.json` was
  re-recorded at the lane head so the freeze test holds the new request.
- **Web search offered to the fast shape is not used for a plain price**
  (`probes/nike-fast-web.json`: one finance call, the provider page cited), so
  it would not have given a quote a publisher.

## The live eval case

`ordinary_conversation_price_question_en` pins `research.published: true`.
Three live runs are kept: `eval-case-nike-live-1.json` failed a row floor the
case briefly carried, because the harness environment left the ticker
unresolved and the two-step budget answered "could not be retrieved";
`eval-case-nike-live-2.json` passed on `published` alone with the same
answer; `eval-case-nike-live-3.json`, at the lane head with the four-step
budget, passed with the quote and one typed row. Whether the provider delivers
a figure on a run is the provider's, so the case pins only what a rule could
take away.

## The money

Every gpt-5.6-sol invoice since 2026-09-03 bills $4 input, $20 output, $5
cache creation and $0.40 cache read per million tokens; the published page
still lists $5, $30 and $0.50, and the 2026-08-07 recording was billed at the
page. The evidence is in `tests/research/fixtures/README.md` and the fourteen
recordings under `docs/reports/evidence/545/probes`. A second reader defect
surfaced from those recordings: a cache bucket nothing was billed in arrives
without its key, and the reader called the whole invoice invalid. After the
change every transcript above carries its real `cost_usd`. The fallback
recorder's production failure could not be observed from this machine (the
Render token had expired and the hosted ledger read was refused); it now logs
the exception that stopped it.

## Spend

Roughly $1.60 of provider calls across the transcripts, probes and the three
eval runs, plus the interpreter and judge calls on OpenRouter.
