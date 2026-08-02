# Experience-audit evidence contract

## Per-scenario record

Capture:

1. Scenario id and owner surface.
2. Founder intent and user value.
3. Persona, branch, exact SHA, flags, and environment mode.
4. Exact prompt, clicked action, keyboard input, and conversation continuity.
5. Expected visible behavior and forbidden outcomes.
6. Actual visible text, cards, actions, attention markers, and reload result.
7. Canonical strategy/draft state, lifecycle, artifacts, jobs/runs, usage,
   receipts, and cost when relevant.
8. Browser request status and console/page errors.
9. Sanitized screenshot path and SHA-256.
10. Commendations that must remain intact.
11. Technical unknowns, hypotheses, and founder decisions in separate lists.
12. Historical PR/commit lineage marked as reference evidence only.

## Evidence language

Use these forms precisely:

- **Observed:** directly visible or read from durable typed state.
- **Proven:** reproduced under a controlled comparison.
- **Inferred:** best explanation supported by evidence but not isolated.
- **Unknown:** evidence is insufficient.
- **Expected:** canon or accepted product direction supports the behavior.

Do not call a correlated database, provider, browser, or console event causal
without isolating it.

## Screenshot rules

- Preserve the original pixel evidence when supplied by the founder.
- Copy it into a stable report asset directory; do not depend on clipboard or
  temporary paths.
- Use a descriptive filename and record its SHA-256.
- Sanitize credentials, cookies, tokens, private metadata, and trace headers.
- Verify every Markdown link after writing the report.

## Current-head rule

A screenshot from an older checkpoint remains valid evidence of that session,
but it is not automatically a current-head defect. Before creating an issue:

1. Identify later PRs touching the owner surface.
2. Reproduce on current integration when safe.
3. Mark unreproduced items as historical evidence needing revalidation.
4. Preserve the original evidence even when current head is green.

## Issue-ready handoff

An autonomous implementation issue must include:

- one bounded outcome and owner;
- exact current-head reproduction or explicit product-gap statement;
- expected behavior and protected commendations;
- evidence paths/hashes;
- deterministic and browser acceptance criteria;
- provider budget and allowed replacement policy;
- forbidden surfaces and hosted-mutation boundary;
- exact stop conditions.
