# Parked interpreter rewrite snapshots

This branch is frozen unfinished work, not a release candidate. No source repair
was made while parking it. The combined scratch tree is the visible tree; its
five parallel variants remain complete, reachable Git commits listed in
[worktrees.json](worktrees.json). Read a variant with `git show <commit>:<path>`.
This preserves conflicting unfinished work without claiming it was reconciled.
All six changed source workspaces were committed; clean baselines stayed clean.
Existing four full live runs remain under `docs/reports/evidence/registry/`.

The [56-run comparison](interleaved/) retains the completed native outputs and
provider answers. Baseline: 25 passed, 3 failed; candidate: 15 passed, 13 failed.
Two apparent candidate passes (33 and 44) have inconsistent judge verdicts and
are invalid acceptance. Recorded cost is $2.609979026294, a lower bound with
unknown timeout/unpriced charges. Matching input hashes do not mean matching
native grading contracts. There is no passing scorecard or fingerprint reset.

Provider reasoning fields were removed from the archived response copies;
answer content, response IDs, usage, grades and exact judge request payloads
remain. Originals were not modified. [response-redactions.json](response-redactions.json)
records both hashes and every removed field. Original analysis refers to the
original hashes; archived-analysis uses the archived copies. Offline comparison
confirmed identical grades, comparisons, costs and readiness. No provider call
was made for this check. [preservation-check.json](preservation-check.json)
also verifies that every committed worktree file matches its pre-commit hash.

Artifact-only scratch and unchanged source archives remain on disk. Generated
build output, dependency symlinks, credentials and environment files are not
source changes and are not added to this branch. The declaration lane proceeds
separately and must retain integration's model-facing files unchanged.
