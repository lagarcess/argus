# Publisher honesty: evidence (#579, #580)

Two fixes in `src/argus/agent_runtime/research_grounded.py`: `881de0e8` dates a
research question by the New York calendar (#579), and `e1f67bd0` withholds an
answer that retrieved nothing (#580), with `72c0bf6a` from Codex review round 1
putting that check before any publisher requirement. Lane base and current
integration are both `3ceada30`. Everything here ran at code head `72c0bf6a`
with no provider key set, and no model or provider was called.

## Replay of the recorded packets

`drivers/replay.py` serves each recorded provider response to the rail's own
client and composes it in one source tree, at the instant it was recorded,
through the inline entry or the background completion. `replay/before.json` is
integration `3ceada30` (exported with `git archive`), `replay/after.json` is
`72c0bf6a`, and `replay/comparison.md` is the table.

The packets are the eleven provider responses #578 recorded under
`open-the-gates/`: its probes and its side-by-side provider calls. None of
them called no tool, so three recorded zero-tool responses are added:
`377/probes/equity_control_quote.json`, `377/probes/equity_peers_netflix.json`
and `545/probes/market_pulse_retry_finance_only.json`.

Five rows change, and only these:

- `perplexity-spx-week`, "how much did the S&P 500 move this week?" asked at
  00:13 UTC. The question date moves from 2026-09-10 to 2026-09-09 and the
  sources go from none to two, vittarthi.com and fred.stlouisfed.org, both
  dated 2026-09-09. Its code is `survey_synthesis_incomplete` in both trees:
  this recording is the plain provider call, whose prose names no ticker the
  synthetic resolver verifies.
- `377-equity-control-quote` (inline and background) and
  `377-equity-peers-netflix-background`: published before,
  `research_not_grounded` after, reading "I couldn't retrieve the data to
  answer this question."
- `377-equity-peers-netflix`, the same response asked as a company read:
  `research_unavailable_missing_public_sources` before, `research_not_grounded`
  after, because a response that retrieved nothing never had a page to find a
  publisher on.

Unchanged: every Nike quote, including `nike-fast-1`, the turn #578 reopened
with one finance lookup; the NVDA claim and its five publishers; the Apple
quotes; and the zero-tool survey, `survey_not_grounded` in both trees. Seven
further rows carry a question date one day earlier and nothing else changes.

## Browser

`browser/replay_api.py` seeds a memory-persistence API with the question clock
frozen at 20:17 in New York (00:17 UTC on 2026-09-10). `browser/drive.mjs`
opens the conversations with Playwright at 1280 and 390 CSS pixels in both
languages, and `browser/report.json` records what each page said and the head
the seed composed at.

- **The S&P week answer shows its sources.** The button reads "2 sources ›"
  and "2 fuentes ›", the drawer "Sources Argus read" and "Fuentes que Argus
  consultó", listing lasvegassun.com and thestockmarketwatch.com
  (`spx-week-answer-*`, `spx-week-sources-*`). The recorded turn,
  `open-the-gates/after/argus-spx-week.json`, had this answer and these rows
  with `sources: []`. Its provider response was not kept, so the seed rebuilds
  it from that transcript's own answer and twelve typed rows: the two cited
  pages are its search results, dated 2026-09-09 as #579 records, and the SPY
  price row cites the provider's finance page, which parsing scrubs to the
  null the transcript shows. The Spanish conversation reuses the English prose
  the provider wrote, so it proves what Argus writes around that prose.
- **A zero-retrieval answer shows the withheld note.** The recorded
  `equity_control_quote` response, composed as a live quote on Apple, reads
  "I couldn't retrieve the data to answer this question." and "No pude
  recuperar los datos para responder esta pregunta.", with no sources button
  and none of the recorded response's own prose (`not-grounded-*`).

The lane web server needs `NEXT_PUBLIC_ENABLE_SPANISH=true` and
`NEXT_PUBLIC_RESEARCH_RAIL_ENABLED=true`, the values `render.yaml` sets.
Without the first, the Spanish page renders English chrome.

## Decisions the tests pin

- A page dated one day past the question date is kept and two days is dropped
  (`test_a_page_dated_one_day_past_the_question_is_kept_and_two_days_is_not`).
  No civil clock is a full day ahead of New York, so a publisher stamping
  pages in UTC dates a page written this New York evening tomorrow. The New
  York date is never later than the UTC date and the upper bound gained a day,
  so nothing the old bounds kept is dropped now.
- A packet that retrieved nothing is classified before any publisher
  requirement, on both paths
  (`test_a_claim_that_retrieved_nothing_is_not_grounded_before_it_lacks_a_publisher`).
  The one publisher retry still runs.
- The background completion shares the retrieval gate.
  `compose_completed_research` published a thorough answer that retrieved
  nothing just as the inline path did; before #578 both paths shared
  `_withheld_code`.

## Left as is

- An explicit relative period the interpreter dates, such as "today", still
  starts from the server's date on a UTC host after 20:00 ET, because the
  interpreter's prompt reads `date.today()`. Today's date has about thirty
  readers in interpretation and changing one would split them, so it is filed
  as #586 (Codex review round 1).
- `research_rows.py` and `_latest_close` still end their price-fetch windows
  on the UTC date. Those bound market-data requests, not publisher pages.

## Spend

None. A live check of the S&P week question after 20:00 ET in both languages
would cost about $0.35 to $0.70: $0.16 per balanced turn as recorded, up to
one survey retry each, plus the interpreter. It was not run. A zero-retrieval
answer cannot be produced on demand live, because whether the model retrieves
is the model's choice.
