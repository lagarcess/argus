# Docs-only CI checks

The policy introduced in [PR #668](https://github.com/lagarcess/argus/pull/668)
is unchanged: docs-only PRs run docs-checks and ownership-gate; the existing
heavy jobs may skip. See [the integration verification rules](specs/private-alpha-next-integration.md#verification-expectations).

## Test selection

[The selector](../.github/docs-reading-tests.sh) conservatively finds Python files
under `tests/` containing `docs/` or a quoted `docs` path component. It selects
direct test readers and, for helper/conftest readers, their entire folder.
Pytest owns recursive collection and exclusions; helpers are never passed as
explicit test files. Covered descendants are removed to avoid duplicate runs.
This is intentionally not import/dependency analysis or changed-file matching.
A helper at the root of `tests/` selects the whole backend suite. Current
promotion-evidence helpers have that shape. Folder selection can therefore cost
more than the previous incomplete reader list; it does not enable other jobs.
Docs-checks installs the same pinned Bun and frontend dependencies as backend-checks
because selected backend tests execute the shared TypeScript contract and canary
session tools. It does not run frontend lint, tests, build, or browser jobs.

Search failures propagate. A successful search with no matches returns an empty
list, which the workflow rejects before pytest. Both command captures preserve
failure status, including failures after partial output.

## Changed-document local-file policy

[The checker](../scripts/check_docs_links.py) checks added/modified `.md` and
`.markdown` files under `docs/` in `BASE...HEAD`. Renames are treated as deletion
plus addition. Deleted documents and unchanged historical documents are not
opened. All links in each changed document are checked, including existing links
in that document; this does not scan the entire historical documentation tree.

It reuses the installed CommonMark parser for inline links, images, reference
links and nested/escaped destinations, plus HTML `href`/`src` attributes.
Inline/fenced code and HTML comments are examples, not checked links.

- Relative paths resolve from the document's directory.
- Leading `/` resolves from the repository root, including links to code.
- Percent escapes are decoded; spaces, parentheses, file and directory links work.
- Query strings and fragments are ignored; heading/anchor validity is not checked.
- External schemes (including HTTPS and mailto), protocol-relative URLs, and
  fragment-only links are ignored. There are no network requests.
- Destinations must exist inside the repository. Traversal or symlinks outside
  the checkout fail. This also applies to a changed document itself.
- Bare prose/code paths, undefined reference labels and application-specific
  templated links are not a Markdown local-file contract. Use a real link to
  make a local dependency checkable. HTML `srcset` is outside this small check.

Run with `poetry run python scripts/check_docs_links.py --base <base-sha>`.
Invalid bases, unreadable files, and checker errors fail the job.

## Aggregation and regression proof

The aggregate accepts only the exact `DOCS_ONLY` strings `true` and `false`.
It always requires classifier and ownership success; docs-only runs also require
docs-checks success. All other success/skipped allowances remain as before.
Failure and cancellation cannot pass under either flag.

[Executable regression tests](../tests/test_docs_ci_gate.py) load and execute
the actual workflow Bash with temporary commands and dependency results.
[Link fixtures](../tests/test_docs_links.py) execute the production checker in
small Git repositories. Hosted backend CI runs these tests under Ubuntu Bash
and Python 3.10. A normal code PR's docs-checks job still skips; a successful
backend fixture run is executable docs-path proof, not a claim that the hosted
docs-checks job ran on that PR.
