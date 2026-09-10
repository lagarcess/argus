# Fourth registry live measurement

**Not accepted: 58 passed, 11 failed, zero infrastructure errors, zero skipped.**
The complete 69-case suite measured clean candidate
`c6c28fefe5b30c1f5d0a67656dc9c6fa025a44e2`, reconciled onto integration
`51086fda2014ddac2aba821a827c7b19234be779` through merge
`42e60ff899178c782573f44570b5f6bd2e20407c`. The interpreter fingerprint remains
unchanged. This record does not clear the lane.

- [Unmodified scorecard](live-measurement-fourth.json), SHA-256
  `7b2876941b4933f1e1a7d5591d6e294fbc17a48ffba7c88c61e2f0e19ca4b67e`.
- [Complete run log](verification/c6c28fef/full-measurement.log) and
  [319 actual completed OpenRouter helper responses](verification/c6c28fef/openrouter-responses.jsonl).
- [Comparison and cost accounting](verification/c6c28fef/measurement-analysis/README.md).
- [Bilingual rowless card browser evidence](browser/c6c28fef/README.md).

The committed wrapper records returned provider response objects without
changing the request, response, suite, or grading. It does not retain judge
request payloads, and local replays must distinguish captured replies from
authored controls. No historical scorecard was regraded.

The estimate announced before this run was **$3–$5**. Accounted reported or
estimated charges are **$2.998189005568**: OpenRouter $2.191359005568 and
non-cached research $0.80683. Seventeen receipt records lack a price, including
five local zero-latency rejection records and twelve timeouts. Unreported
additional charges remain unknown; a receipt row is not a unique request.
The earlier four retrieval-schema recaptures separately cost $0.52122.

All four effective canonical intents occur: calculate 44, follow_up 12,
explain 6, cannot 7. There are 35 zero-call cases and 34 single-call cases.
This run provides no live repeated-call or composed-call proof. Structural
compatibility tests cover the seven historical labels separately.

## Current gates at the measured head

[Backend CI](https://github.com/lagarcess/argus/actions/runs/34443432455)
reports **7,346 passed, 585 skipped, one failure**, the unchanged fingerprint.
Frontend checks, guest release gates, ownership, the non-draft
[agent runtime sweep](https://github.com/lagarcess/argus/actions/runs/34443432485),
and [local smoke](https://github.com/lagarcess/argus/actions/runs/34443432497)
passed. The final review remains owed after repairs and accepted measurement.

Supabase Preview is now successful. Its disposable, nonpersistent PR branch
had no users, storage objects, or product data; only the two repository QA
allowlist seed rows existed. Resetting that preview removed its obsolete tool
receipt migration and applied all 73 repository migrations. Readback reports
`FUNCTIONS_DEPLOYED` and `ACTIVE_HEALTHY`. The [repair record](verification/c6c28fef/preview-repair.json)
identifies the exact preview and before/after migration inventories. No
production database changed and no removed public implementation was restored.

## Recorded failures and next checks

Ten cases that passed in each older fingerprint comparison fail here. Against
the third registry run, eleven failures became passes and three passes became
failures. Source and observation changes prevent assigning every transition to
the catalog; they do not permit erasing failures.

Retained-response controls reproduce an explicit-cost audit applicability
defect, a DCA repair changing call scope before known-fact comparison, and a
benchmark comparison that precedes canonical resolution. The selection judge
also receives internal cache classification as though it describes the user's
requested category. These are bounded repair candidates, with separate
verification required. Remaining provider, relevance, and inherited runtime
failures stay in the scorecard. This is an intermediate evidence record, not a
terminal audit.
