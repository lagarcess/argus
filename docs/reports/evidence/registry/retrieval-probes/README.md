# Current retrieval request recordings

These four raw recordings measure clean merge commit
`42e60ff899178c782573f44570b5f6bd2e20407c`, reconciled with integration
`51086fda2014ddac2aba821a827c7b19234be779`. The repository's existing recording
driver called the real provider without request overrides or `--allow-dirty`.
The previous recordings under `evidence/545/probes` remain unchanged.

The changed response-schema description now describes #578's publication rule:
a row may retain a model citation, and uncited figures publish with a source
limitation. Provided numeric rows still validate against their typed schema.

| Recording | Result | Typed rows | Reported and parsed cost |
| --- | --- | ---: | ---: |
| fast_quote_typed | completed | 1 | $0.04384 |
| typed_rows_current_external | completed | 2 | $0.22326 |
| domain_filtered_local_source | completed, no rate figure retrieved | 0 | $0.06843 |
| thorough_typed_background | completed | 10 | $0.18569 |

All four returned HTTP 200 and a nonblank typed answer. Costs total
**$0.52122**, within the announced $0.40–$0.80 estimate. Each provider invoice
agrees with the current parser; the background submit and completed response
are one billed operation. The bank result does not establish that Argus found
the requested rate. Raw requests, responses, packet projections, timestamps,
and candidate SHA are preserved in [42e60ff8](42e60ff8/).

`test_retrieval_contract_probe.py` compares today's instructions, response
schema, models, step bound, and tools against these requests. Historical
behavioral probes retain their original recordings and assertions.
