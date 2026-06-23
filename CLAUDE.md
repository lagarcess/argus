# Argus Claude Review Contract

Read `AGENTS.md` first. It is the primary operating guide for this repo.

For any code review, also use:

- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- the active roadmap, lane spec, or release document for the change

Review against the named parent branch. Do not assume `main` is the correct
comparison base for stacked or lane work.

Focus review on:

- user-visible regressions;
- Argus language-agnostic runtime spine;
- no regex, hardcoded language gates, or shortcut routing before LLM
  interpretation;
- backend canonical truth and Supabase persistence ownership;
- frontend rendering backend-provided state instead of inventing state;
- API contract and OpenAPI/doc consistency;
- modularity, large-file drift, and mixed concerns;
- focused tests, browser QA, and release-gate evidence gaps;
- Render/workflow/canary promotion discipline.

Do not suggest broad rewrites, future-slice work, or new product surfaces unless
they block the active lane. Prefer concrete findings with file and line
references, severity, impact, and the smallest safe fix.

For development reviews, use local on-demand Claude Code review commands on a
bounded diff. For promotion candidates, use a manual or label/comment-triggered
GitHub review gate. Do not run Claude review automatically on every push.
