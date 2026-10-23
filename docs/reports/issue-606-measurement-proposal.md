# #606: built, measurement approved but on hold

This is a pre-measurement handoff. The PR stays draft until measurement and
refreeze are complete. No paid measurement or Codex review has run.

- Branch: `codex/606-result-followup-single-list`.
- Original integration base: `350e3dca8f573f5dfd61f1f753d8ed16a2724c9e`.
- Latest fetched integration: `538aec3a9947caf8eb290a1f87551a2212496d44`.
- One-way reconciliation merge: `86f1f38e1f8254c3e3b5eb09e2131a867eef72ba`.
- Founder approved **$12.50 or 30 minutes combined**, whichever comes first,
  with no automatic retries. Start remains on hold until the founder sends go
  after the other measurement frees the paid slot.
- Provider authorization takes effect at that go: the authored fixtures and
  changed model-facing text may be sent to OpenRouter and Perplexity.

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

The implementation preserves the frontend runtime, action contract, routing,
`render.yaml`, and release contracts.

## Integration overlap

The merge completed without conflicts and preserves both branches. Integration
changed research asset identity and same-class validation, typed peer identities,
and chat transcript refresh after replies from another tab. These share the
research/action and chat surfaces exercised by this lane. Integration did not
change the result-conversation prompt module.

The original renderer evidence remains applicable. Rechecked research identity,
confirmation peers, research rows, next-step controls, and transcript reload
against the merged tree. No lane-owned migration or environment change is needed.
There is no previous paid evidence to retain or invalidate.

## Free verification

- Prompt regression: four failures before the fix, covering both languages and
  both search settings; all four pass after it.
- Merged backend and mocked harness selection: 386 passed. This includes 18
  measurement preparation tests; the added baseline admission regression brings
  the preparation selection to 19 passing tests.
- Merged web selection: 41 passed across `chat-next-steps`, `next-experiments`,
  `confirmation-peer-identity`, and `conversation-activity-transcript-reload`.
  Full message rendering preserves the fact paragraph and shows four ordered
  controls once in each language, including runnable tests and questions.
- Ruff, focused ESLint, `git diff --check`, and the merged-tree modularity budget:
  passed.
- Prompt-freeze suite: 1 expected failure, 2 passed. Only
  `src/argus/agent_runtime/result_conversation.py` reports surface drift.
- Offline runner preview: all six fixture/language combinations build real
  composer requests and sidecars, with zero provider calls. Preview models derive
  from the committed release profile. The regression clears local model settings
  and credentials, reproducing the configuration-free CI environment.

Authored responses prove the rendering contract, not live model compliance.
The fingerprint is unchanged. Hosted CI is reported on the draft PR at its head.

## Prepared measurement

The committed entrypoint is `tests/evals/result_followup_measurement.py`. It is
fully offline by default. `result_followup_measurement_probe.py` uses the actual
result fact bank, composer, sidecars, and provider request builders. The fixture
file covers DCA, buy and hold, and moving-average crossover in English and
Spanish. Its completed-result packets are explicitly authored, not fresh engine
runs or empirical measurement evidence.

The runner uses a clean candidate commit and a clearly labeled synthetic
baseline: the same candidate archive with only `result_conversation.py` restored
from integration `538aec3a`. This keeps the reconciled runtime constant while
isolating the prompt change. Both source hashes and effective release
configuration are recorded. The baseline archive validates credential provenance
against the candidate repository, since the archive has no Git metadata.

1. Run six sequential baseline/candidate pairs, twelve result-follow-up turns.
   Cover the reported gap/costs/drop-dates/next-test question, a next-test ask
   through the no-search path, and an explanation through the research path.
2. Compare each delivered answer and structured list: suggestions appear once,
   facts and dates are preserved, tests and questions share one order, action
   payloads work, language is correct, and visible copy has no em dashes. Render
   captured outputs offline to check controls without paid browser turns.
3. Run the full native live measurement entrypoint once. Compare every case with
   the frozen scorecard, retaining exact-head provenance, costs, and traces.
4. Refreeze only after the paired and native comparisons show no regression.
   The runner leaves semantic review pending and never refreezes automatically.
   On regression or incomplete execution, stop and report cases and traces.

### Budget admission

One persistent ledger covers both providers, all pairs, and the native suite.
Before dispatch it reserves the highest complete per-model cost ceiling across
the Agent client's `models` fallback list. Tests build the body with
`PerplexityAgentClient._request_body` and exercise the actual client through
mock HTTP, including reversed fallback order, unpriced models, and HTTP 429.
A priced fallback is accepted regardless of list position; an unpriced model
stops dispatch.

Reservations include model context/output bounds and tools, then settle against
reported invoice cost. The ledger stops on unknown cost, rate limits, provider
failure, repeat requests within a scope, cap exhaustion, or deadline. It refuses
concurrent paid calls and cannot be reset or expanded. Raw local traces contain
requests and responses without authorization headers; sanitize them before
committing evidence.

Rates were checked on 2026-09-15 against the
[OpenRouter model catalog](https://openrouter.ai/api/v1/models) and
[Perplexity Agent model pricing](https://docs.perplexity.ai/docs/agent-api/models).
They are committed in `result_followup_measurement_rates.json`. The research
reservation uses the full model context for a conservative ceiling. A native
suite model/fallback ceiling can exceed the remaining approved budget, in which
case the run stops without a complete scorecard. Completion is not guaranteed
within the cap; limits and model configuration must not be reduced to force it.

### Commands

Free preview, safe before go:

```sh
poetry run python -m tests.evals.result_followup_measurement \
  --rates tests/evals/result_followup_measurement_rates.json \
  --output temp/issue-606-measurement-dry
```

Only after founder go, substitute the exact clean draft PR head for
`<approved-head>` and use a new output directory:

```sh
poetry run python -m tests.evals.result_followup_measurement \
  --live --expected-head <approved-head> \
  --env-file temp/issue-606-measurement.env \
  --rates tests/evals/result_followup_measurement_rates.json \
  --output temp/issue-606-measurement-live
```

The local ignored environment file is prepared with mode 0600 and its effective
release configuration was checked offline. No credentials are committed. The
runner verifies the exact clean head before every child and after the run.
Do not commit during a live run, and do not automatically restart a stopped run.

## After measurement

After a clean comparison, commit the scorecard and refreeze, then mark the PR
ready. Keep it ready while addressing Codex findings at the current head: fix
confirmed findings with tests, decline wrong findings with reasons, reply and
resolve, push, and wait for CI before commenting `@codex review`. Repeat until
Codex is clean and there are zero unresolved threads. Then stop. The founder
retains merge and deployment ownership.
