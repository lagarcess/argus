# Readout demo fixes, September 10, 2026

The founder's live demo found four reachable problems: OpenRouter rejected
Quick take's unsupported temperature parameter, Breakdown received a large
technical fact dump and did not search, reference bookkeeping rejected an honest
repeated count, and the pending Breakdown frame displayed an insufficient-facts
message. This round addresses those four problems on PR #588.

Only readout-tier OpenRouter requests omit temperature. Breakdown now asks
plainly what happened to the asset over the tested window and why, what holding
through it was like, and how the test compared with the benchmark, with sources.
Its request contains labeled headline scalar run facts, never chart series,
markers or internal field paths. The full labeled fact sheet remains the shared
internal source. The existing frames, their order and the card are unchanged;
the pending Breakdown frame uses the existing localized working label.

Both model drafts contain `language`, complete `text` and `figures`. A declared
run reference contains only `fact_key` and its displayed `value`. Perplexity's
returned sources use the existing Sources panel, with their dates when available. Search
context never changes the run facts.

The first repeat-demo Breakdown searched, but changed the supplied fact labels
into underscored names and fell back. The response schema now derives its allowed
reference names directly from the supplied headline labels, so the request and
validation share one set of names. The failed attempt and its bill are retained
in the demo evidence.

| Check | Disposition and reason |
| --- | --- |
| Declared run figure key/value | Stays: rejects an unknown fact or a declared value outside display rounding; counts and calendar dates must match exactly. |
| Written language | Stays: rejects a model-reported language that differs from the workspace request, protecting saved language ownership. |
| Draft schema | Stays: rejects malformed structured output so the reader receives one complete, valid envelope. |
| Empty draft | Stays: selects the template when the provider returned no usable prose. |
| Provider failure or unavailable capacity | Stays: selects the complete template and records failure metadata instead of showing a partial answer. |
| Run quote and occurrence coverage | Goes: a repeated honest number or missing reference no longer discards the readout; the remaining guard checks declared references only. |
| Web claim quote, occurrence and citation index | Goes: the app shows the Agent's returned sources directly, so the model need not recreate citation bookkeeping. |
| Mandatory web claim date | Goes: provider source dates are displayed when supplied; an absent date is not a prose failure. |
| Run/source numeric-span overlap | Goes: numeric spans are no longer reconstructed; run fact ownership remains explicit in the input and references. |
| Model-written link rejection | Goes: source display derives from returned provider sources without a prose-link rejection rule. |
| Benchmark beat-or-lag regex | Goes: the founder requested one light factual guard; benchmark meaning remains in labeled facts and the writing brief. |
| Internal field-name regex | Goes: plain input avoids teaching internal vocabulary, while plain language remains a writing requirement. |
| Three-figure allowance | Remains removed: an honest useful draft may need more figures, and the card owns the numerical inventory. |
| Required Quick take and Breakdown mentions | Remains removed: each surface should tell its own story rather than satisfy a mandatory metric checklist. |

The light guard does not check every number in free text and does not prove that
a source supports each sentence. Accepted factual errors remain possible and
must be reported in the live demo rather than hidden by a claim of validation.
Language reporting is the model's structured self-report, not an independent
language classifier. All rejected drafts use the existing source, fallback and
failure-mode metadata, and no partial draft crosses the public readout envelope.

The founder authorized a repeat of the real-app English and Spanish demo for
DOCN buy and hold, DOCN DCA with costs, and SPY RSI. The parent task owns that
demo's screenshots, source/search evidence, model-versus-template outcomes and
billed spend, with a stop if spend passes $3. This note records implementation
intent and check dispositions, not a completed live acceptance claim. The prompt
fingerprint remains held. No full measurement or merge is authorized.

## Sources, wording and rounding follow-up (September 11)

The founder's real app review requested three further changes. Breakdown now
transports returned sources through the canonical research sidecar and opens the
existing panel, live and after reload. In-text links remain; no bibliography is
appended. Both composers receive display-ready figures matching card precision.
The brief asks for the holding experience in everyday language and keeps accuracy
reasoning silent; hypothetical capital-scaled losses are absent from model input.
Stored run facts and the light acceptance checks are unchanged.

Verification before the next paid demo: 157 focused backend tests and 82 frontend
tests passed, including real mocked SSE persistence/readback and bilingual panel
projection. Formatter verification separately passed 44 Python tests, 18 web
tests and 16 direct card/helper currency comparisons. Ruff and diff checks pass.
The prompt fingerprint remains held; no full live measurement or merge was run.

Earlier live attempts are retained under `evidence/model-result-readouts/app-demo`
and `app-demo-fixes`, with each provider attempt carrying its source SHA. The
known billed total before this follow-up demo is $0.32597547. Two provider error
responses supplied no billing data. Earlier screenshots are historical findings,
not acceptance evidence for this new source change.


The first Sources-panel demo at `d9152dc0` produced a Luna Quick take and a
searched Breakdown that fell back because numeric references were formatted
strings. The shared instruction/schema description now asks for JSON numbers
and reserves strings for ISO dates; validation is unchanged. That rejected draft
and its $0.01272 bill remain in the evidence. Cumulative known spend is $0.35819697.

CI exposed a web build-context issue with importing the canonical formatting
policy from `src`. The single JSON owner now lives in the small
`web/argus_display_contract` package, included in the Python wheel and imported
locally by the web build. A production Turbopack build using only the web context
passes. The wheel contains the policy and can read it from an isolated installed
layout. Deployment configuration is unchanged. Updated runtime assertions pass
68 focused tests; the packaging/readout regression check passes 102 tests.


At `7141b0dc`, the English DOCN and DCA cases produced both Luna readouts. Sources
were shown live and after reload. Known billed spend reached $0.43636727; the
same two earlier provider errors still have no invoice. Screenshots and source
records are retained even where the accepted wording needs improvement.

The founder then requested one pending Breakdown state instead of two and natural
strategy-action wording. The duplicate is the general streaming-status row in
ChatInterface plus the Breakdown frame's own working label, not the tool-job
row. The follow-up also covers in-flight reload from the durable typed request
lifecycle. The writing brief now describes actions such as buying once and
holding rather than narrating record keeping. Fingerprint remains held.
