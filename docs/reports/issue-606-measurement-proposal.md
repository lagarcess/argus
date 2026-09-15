# #606: built, measurement approved but on hold

This is a pre-measurement handoff, not a readiness audit.

- Branch: `codex/606-result-followup-single-list`.
- Original fetched integration base: `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`.
- Founder authorized committing and pushing this change for free CI.
- No paid calls, live measurement, refreeze, PR, or Codex review round run.
- The measurement proposal is approved within the combined cap below, but must
  not start until another model-facing change lands and the founder sends go.
- Codex review must wait until measurement and refreeze are complete.

## Cause and change

[Issue #606](https://github.com/lagarcess/argus/issues/606) records the same
failure in English and Spanish. The saved English reproduction contains the
correct fact paragraph, four prose suggestions, and four matching controls.
`result_followup_answers.py` preserves the composer's text and attaches the
single structured list from `result_next_steps.py`. `ChatMessage` renders that
text and one `NextStepsSection`.

`result_conversation_instructions` explicitly requested an ordered prose plan
and then requested its steps again in `next_steps`. The fix removes that
conflicting instruction. The prompt and schema now assign suggested tests and
questions only to `next_steps`; `text` keeps the fact answer and explanation.
The next-step instruction is shared between the prompt and schema.

No prose stripping, frontend runtime change, action-contract change, routing
change, `render.yaml` change, or release-contract change is needed.

## Free verification

- Prompt regression: four failures before the fix, covering both languages and
  both search settings; all four pass after it.
- Focused backend suites: 50 passed (`test_result_conversation_wording`,
  `test_result_conversation`, `test_result_followup_answers`, `test_result_next_steps`).
- Mocked harness command from `tests/evals/README.md`: 270 passed.
- `bun test __tests__/chat-next-steps.test.tsx`: 8 passed. Full message rendering
  preserves the fact paragraph and shows four ordered controls once in each
  language. Existing action tests verify runnable and question dispatch.
- Ruff, focused ESLint, and `git diff --check`: passed.
- Prompt-freeze suite: 1 expected failure, 2 passed. Only
  `src/argus/agent_runtime/result_conversation.py` has reported surface drift.

Authored responses prove the rendering contract, not live model compliance.
CI and readiness remain pending. The fingerprint has not been changed.

## Approved paid measurement, start remains on hold until founder go

1. Pin clean baseline and candidate commits and identical runtime configuration.
2. Run six sequential baseline/candidate pairs, twelve result-follow-up turns:
   English and Spanish for each of DCA, buy and hold, and an indicator strategy.
   Reuse fixed completed-result packets. Include the reported combined
   gap/costs/drop-dates/next-test question, an explicit next-test ask through the
   no-search path, and an explanation with questions through the research path.
3. Inspect every delivered answer and structured list: no repeated suggestions,
   fact figures and dates preserved, tests and questions in one order, valid
   action payloads, correct language, and no em dashes. Render captured outputs
   and verify controls offline, without additional paid browser turns.
4. Run the required full native live measurement suite once; retain exact-head
   provenance, costs, and its comparison with the frozen scorecard. The small
   paired check alone is insufficient to refreeze.

Combined limit: **$12.50 and 30 minutes**, whichever is reached first. Reserve
the next request's maximum cost before dispatch, including tools, fallback and
judge work. Stop if pricing or usage cannot be bounded, on provider rate limits,
or on a second finding involving this mechanism. No automatic retries or extra
paid browser sessions. An incomplete run stays incomplete and does not refreeze.

After acceptable measurement and authorization to refreeze: preserve evidence,
complete one Codex review round, and finish only with green CI and zero unresolved
threads before marking ready. Stop and report a second finding on this mechanism.
