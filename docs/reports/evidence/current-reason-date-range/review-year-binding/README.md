# Codex review: bind typed endpoints once

Codex reviewed `06c6ebfb976179fc67209919e81c08de3ff8f9d3` and found that
`since` windows did not carry `year_reference=current_year` to date resolution.
The same branch-local omission applied to the explicit end of a rolling window.

The fix resolves typed year, start and end once at the existing date-intent
boundary. Every window kind consumes those clock-owned values. An invalid
current-year leap day is rejected before any branch can replace it with a
default; user-stated historical years remain intact. This removes duplicated
binding logic. No prompt, response schema, fixture, judge, provider setting or
language parser changed.

Eleven regression assertions failed before the fix; all 153 focused date,
interpreter-boundary and prompt-freeze checks passed afterward. The tests cover
English/Spanish focused extraction, yearless and stale ISO endpoints, since
windows with an omitted end, year-only since windows, invalid leap dates,
historical-year preservation, and a rolling window's typed end. Repository lint
and merged-tree modularity passed. The complete mocked harness also passed.

A provider-free replay compares every saved structured date intent from the
accepted full run against the measured resolver and the review-fixed resolver.
All 30 saved intents across 23 cases are unchanged for both New York dates
spanned by the run, 60 comparisons total. The exact extraction/replay script and
output are retained. This is a deterministic impact check, not another live
measurement and not a claim that the runtime commit is identical to `6e9e6d7e`.

The accepted 73-case scorecard and fingerprint retain their actual measured SHA.
The review fix follows the founder's instruction to fix confirmed Codex findings
with tests while keeping the PR ready. No additional paid call or refreeze was
performed. Final CI and the delta review will be recorded on the PR.
