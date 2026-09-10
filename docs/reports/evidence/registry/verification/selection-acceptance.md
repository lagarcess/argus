# Collective selection acceptance

Fresh catalog observations use `argus-selection-evidence/v1`. This is an
evaluation-contract correction, not a runtime or fixture change. It removes the
requirement for a `peer_expansion` call and checks the same user request against
the collective delivered evidence. The fixture messages, expectations, original
prose criteria, interpreter surface, and historical scorecards are unchanged.

Previously the evaluator selected only `peer_expansion` argument dictionaries
and required one dictionary to contain every discovery field. A valid screen or
composition could fail before its results were examined. Actionability also
counted next-experiment kinds without retaining their asset identity.

The new projection reads matching actual calls, execution records, completed
typed results, delivered cards, and their bound effects. Argument normalization
comes from the declaration solely to verify the call binding; arguments never
become result evidence. Card type and version must match the declaration's
binding, and its existing return validator must accept the result before the
common research envelope can project facts. Resolver-owned subjects and
`ValidatedCandidate` rows provide identity and asset class. The final discovery rows and typed ticker/name
parts of final actions establish what the user can select. Earlier result cards
can contribute evidence, but overwritten actions do not count as delivered.

Candidate source indices and cited figure URLs must link to retained sources
delivered with the same result. Current selections require a retained retrieval
timestamp within the shared `movers` freshness limit and sources admitted by the
existing current-survey source-selection policy. A request flag, invoice, or
unrelated citation cannot establish currentness. Missing class, source linkage,
timestamps, or identity is reported as unproven. A same-ticker, different-entity
action fails through the existing asset-name corroboration owner.

Category, relationship, and anchor relevance use one generic
`selection_relevance` criterion in the existing prose-judge invocation. The judge
receives the unchanged fixture expectation and collective delivered facts,
without call/artifact identifiers or raw arguments. This adds context to the
existing call; it adds no model invocation. Its contract version, requested
criterion, expectation, and evidence are retained in the fresh result. Disabling
the judge leaves relevance unproven; an unavailable judge blocks the gate. A
passing judge cannot override a structural failure. Existing offered-content and
applicable limitation/disclosure assertions remain active.

Legacy fixtures without the declared-dispatch expectation retain their original
typed input-payload comparison. The retained
[screening probe](262d670f/interleaved/26-candidate-r2.json) and
[peer-expansion probe](262d670f/interleaved/11-candidate-r1.json) keep their original
grades and provenance. Neither has been regraded with this contract. A future
live gate must measure the new contract on its own clean candidate.

The mocked regression uses the production execute stage and card presenter with
authored local handlers and existing research/asset factories. The initial red
run had five failures: three valid alternate/composed deliveries, a wrong-asset
action, and a missing relevance check. The completed matrix covers alternate,
multiple, repeated and zero calls; per-call identity mutations; pending results;
missing/stale source evidence; source-index linkage; wrong-entity actions;
final-action visibility; relevance rejection/outage; and legacy compatibility.
Review added three mutation controls that first reproduced false acceptance:
wrong card type, wrong card version, and a compatibility-envelope result that
violated the callable's narrower declared return. All now fail structurally;
a valid narrow return remains accepted.
No provider calls were made for this repair.

Verification: [30 focused cases passed](selection-focused.txt), and the normal
free mocked command from `tests/evals/README.md`, with
`test_measurement_eval_issue_498.py` and `test_measurement_selection.py` included,
[passed all 357 cases](selection-mocked.txt). Ruff, formatting, the whole-tree
diff check, and the combined modularity check passed. The harness is 1,220 lines
against its 1,250-line limit.
