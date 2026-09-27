# Issue #670: docs-only CI hardening

## Outcome and authority

Implement [issue #670](https://github.com/lagarcess/argus/issues/670), following
[documentation authority](../../DOCUMENTATION_AUTHORITY.md). This CI maintenance
slice preserves product/runtime contracts and the skip policy from PR #668.
Integration base: `ab9143c18740c28f582646d405445c01c4c8aff4`.

## Locked scope

- Discover Python documentation readers, including helpers and conftests.
  Pass helper folders to pytest so pytest owns recursive collection rules.
- Propagate discovery failures and reject empty selections before pytest.
- Require the aggregate flag to be exactly `true` or `false`.
- Execute workflow Bash directly in tests; do not duplicate its decision logic.
- Check local Markdown link/image destinations in added/modified Markdown under
  `docs/` against the PR merge base. Use the existing Markdown parser. Resolve
  relative links from the document, leading slashes from the repository root,
  and percent escapes before checking existence. Permit files and directories;
  reject escapes outside the repository. Ignore external schemes, protocol-relative
  URLs, fragment-only links, query/fragment suffixes, and code examples. Parse
  reference links and HTML href/src too. No HTTP requests or anchor validation.
  Deleted documents and unchanged historical documents are outside this check.

## Execution and verification

Own the selector, docs-checks selection/link steps, aggregate validation,
focused tests, and CI documentation. Preserve unrelated edits. Reproduce failures
with temporary repositories and commands, then run focused pytest and lint,
ownership verification, merged-tree modularity, and actual hosted workflow checks.
Review/fix the PR until the latest delta is clean with zero unresolved threads.
Record exact head, integration reconciliation, retained evidence and unavailable
checks before claiming readiness. The endpoint is a reviewed PR for founder merge.

## Stop conditions

Do not change job skip policy, deployment triggers, repository settings, runtime
code, product authority or roadmap. Escalate any acceptance conflict requiring
those changes. Do not merge, deploy, or close the issue without acceptance evidence.
