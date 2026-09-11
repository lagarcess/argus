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
returned sources are appended as links, with their dates when available. Search
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
