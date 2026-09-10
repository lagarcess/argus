# Fourth-run comparison and accounting

The input is the unchanged 69-case scorecard at clean `c6c28fef`.
[provenance.json](provenance.json) records original input paths and hashes;
the copied scorecard, log and actual response JSONL are retained in this PR.
[analyze_scorecards.py](analyze_scorecards.py) imports only read-only comparison
helpers from the committed third-run analysis. It does not regrade cases.

Reproduce from the repository root:

```sh
.venv/bin/python docs/reports/evidence/registry/verification/c6c28fef/measurement-analysis/analyze_scorecards.py \
  --root "$PWD" \
  --scorecard docs/reports/evidence/registry/live-measurement-fourth.json \
  --log docs/reports/evidence/registry/verification/c6c28fef/full-measurement.log \
  --responses docs/reports/evidence/registry/verification/c6c28fef/openrouter-responses.jsonl \
  --output /private/tmp/registry-fourth-reproduction
```

[comparison.json](comparison.json) preserves case/check transitions against
fingerprints 411 and 565 and the third registry run. The candidate has 58 passes
and 11 failures. Each historical fingerprint comparison has ten pass-to-fail
transitions; the third-run comparison has three pass-to-fail and eleven
fail-to-pass transitions. These are observed transitions, not isolated causal
estimates across different source and harness versions.

[cost-accounting.json](cost-accounting.json) verifies every retained route
receipt against the run log and every final grade against its completion event.
It sums non-null OpenRouter charges and non-cache-hit research usage. Cached
packet prices are not billed again. There are no unpriced research invoice log
entries in this run. Unknown OpenRouter timeout charges remain unknown; five
local zero-latency rejection records do not imply five provider requests.

The 319 captured response rows retain completed HTTP helper returns, including
model validation failures, and bind them to candidate SHA and case. Provider
requests and headers were not captured. A missing response is not reconstructed
as an actual provider return. Controlled replay fixtures must say which parts
were authored.
