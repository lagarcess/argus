# Explicit-cost audit applicability

The actual retained primary correctly supplies both costs, selects no calls,
and labels the turn `follow_up/new_idea`. The later canonical strategy owner
recognizes that combination as preparation, but the cost audit previously
admitted only the `calculate` label. Ungrounded costs then disappear before
confirmation.

The repair derives eligibility from the existing `strategy_route_expected`
owner, preserving refusal, result-follow-up and approval exclusions. No
model-facing text changes. The regression test's primary equals
[primary.json](primary.json); its sibling intent and successful grounded audit
reply are explicitly authored controls. Sockets are forbidden.

- [Red](test-red.log): two failures, thirteen passes.
- [Green](test-green.log): fifteen passes.
- [Shared owners](test-shared-owners.log): 119 passes across cost fidelity,
  confirmation preservation, admission exclusions and the new full-graph test.

The full-graph control reaches `await_approval` with `explicit_user` cost
provenance and the actual launch realism payload. This is provider-free
verification, not a new live result or permission to update the fingerprint.
