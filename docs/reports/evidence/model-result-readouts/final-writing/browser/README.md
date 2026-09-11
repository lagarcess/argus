# Luna readout round: offline browser harness

Prepared under spec section 9, which supersedes the unpaid section 8 experiment.
No measured Luna draft or screenshot is
claimed by this preparation. The parent must obtain the new cost approval and
complete the twelve single-attempt tasks before this harness consumes their
report. Browser replay itself makes no provider, market-data or backtest calls.

The flow under test is: open a locally seeded saved conversation, change the
workspace language through Settings, inspect both actual readout frames, copy
each frame, and reload without changing its saved text or stored source facts.

## Inputs and provenance

`replay_data.py` consumes the existing measurement report's six paired rows:
three `recorded-fixtures.json` cases, `en` and `es-419`, candidate variant, one
repetition. Quick take uses OpenRouter's `readout` tier; Breakdown uses
Perplexity Agent. Each frame consumes `accepted_text`, full composer outcome,
source/fallback/failure metadata and exact per-task request/response receipts.
Missing outcomes become complete frontend fallback. A raw draft is never
promoted to accepted text. More than one provider request per frame is rejected.
Actual proof must declare `live_targeted`, `luna` comparison mode, twelve
scheduled tasks and one attempt per task. Free preflight reports are refused.
The superseded structured-tier writing report is also refused. Configured and
observed providers must match each frame; mixed-provider receipts and raw
responses remain separated by task and attempt ID.
An absent frame requires a recorded interruption; it cannot silently turn an
unfinished or preflight report into a completed fallback outcome. Rejected
content checks inspect both the raw response and parsed Markdown text.
Accepted Breakdown Markdown, including code-attached dated citation labels and
URLs, passes unchanged through the existing envelope. Capture compares every
rendered link label and href with that accepted Markdown and retains clipboard
parity. Links are inspected, never opened. No external page is fetched.

The original fixture manifest and its three canonical source JSONs must still
match their recorded hashes and contents. Local run/conversation IDs and
readout metadata are reconstructed only in memory for transport acceptance;
saved source files and old evidence remain unchanged. The DCA source is a
genuine direct engine run; it is not a successful DCA chat journey.

The reader SHA and measurement checkout SHA are recorded separately. Both API
and web launchers require the requested current reader SHA and clean `src/` and
`web/` source. The final capture verifies every copied web file and loaded
reader file before and after capture. An evidence-only later commit requires
explicit source revalidation by the parent.

## Guards and isolation

- API: `http://127.0.0.1:8541`; copied web: `http://127.0.0.1:3221`.
- Only existing `.venv`, Bun, repository Playwright 1.59.1 and installed
  Chromium are used. No install/download is required. Browser plugin is not
  available, so the existing repository Playwright path is used.
- Both child environments use a short credential-free allowlist. No dotenv
  file is read or written. The API disables dotenv before Argus imports,
  uses mock auth and memory persistence, and rejects non-loopback DNS,
  `socket.connect` and `socket.connect_ex`.
- The API rejects every mutation except the local mock profile's Settings
  PATCH. Browser request interception independently rejects external requests
  and those same forbidden mutations. Generation/backtest requests cannot pass.
- Web tracked files are copied into temporary storage excluding `.env*`.
  Existing `node_modules` is symlinked. Next writes only in that temporary copy,
  which the launcher removes when stopped. No production configuration changes.
- A successful capture requires zero browser/backend blocked attempts, zero
  console warnings/errors, zero page errors and unchanged stored artifact and
  source-file hashes. A failed check remains a failure; the harness never
  invokes a model to repair it.

## Commands

Run from the repository root. The output directory must be this browser
evidence directory (or temporary storage for explicitly synthetic checks).
Use the reader SHA actually being vouched for, not an example SHA.

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/reports/evidence/model-result-readouts/final-writing/browser/check_harness.py
node docs/reports/evidence/model-result-readouts/final-writing/browser/check_markup.cjs
node --check docs/reports/evidence/model-result-readouts/final-writing/browser/capture.cjs
```

After paid outcomes exist and the parent pins the reader:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/reports/evidence/model-result-readouts/final-writing/browser/replay_api.py --report /absolute/path/to/final-writing-report.json --sha READER_SHA
```

In another managed terminal:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/reports/evidence/model-result-readouts/final-writing/browser/start_web.py --sha READER_SHA --output docs/reports/evidence/model-result-readouts/final-writing/browser
```

Once the copied web server is ready:

```sh
node docs/reports/evidence/model-result-readouts/final-writing/browser/capture.cjs --output docs/reports/evidence/model-result-readouts/final-writing/browser
```

Stop both managed terminals after capture; confirm ports 8541 and 3221 have no
listeners. Retain the web-source cleanup receipt. No servers are started by
the preparation/schema check.

## Planned durable screenshots

Each of the twelve tasks produces:

1. `<case>-<locale>-<surface>-frame.png`: actual Argus frame screenshot, with
   its unchanged label and complete accepted text or complete frontend fallback.
2. `<case>-<locale>-<surface>.png`: a full evidence sheet placing that exact
   frame image beside the same run's canonical source-number table. Source
   values and paths are copied exactly, without rounding or recomputation.
   Dense chart points and trades remain in the unchanged full source JSON.
3. For rejection/unavailability, a separate **DIAGNOSTIC ONLY** section holds
   the complete returned raw draft, including malformed JSON. It is never
   inserted into the product frame. If absent, the sheet explicitly says so.
4. Frame DOM snapshot, exact text/copy/source/receipt JSON and the HTML evidence
   sheet. The HTML contains the real frame image; it does not recreate Argus UI.
   Every sheet identifies its frame's provider. Any returned web sources appear
   in a separate external-context provenance panel, never merged into the
   canonical backtest source-number table. Rejected source/raw evidence remains
   diagnostic even if some of its citations are valid.

`proof.json` records all twelve outcomes, locale switches, reload/copy parity,
browser health, source hashes and the zero-call guard results. Actual PNGs must
be opened and visually inspected before claiming browser acceptance. These
are renderer/transport screenshots of existing measured drafts, not fresh
backtests, a new model-quality measurement, or a deployed preview.

Existing bilingual mismatch/legacy regressions remain in `../../browser/` and
`../../live-browser/`; this bounded round does not rewrite those histories or
repeat a large matrix. New screenshots remain pending the twelve actual
approved Luna outcomes.
