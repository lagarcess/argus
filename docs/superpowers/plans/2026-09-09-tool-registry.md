# Tool registry implementation plan

> For agentic workers: use the subagent-driven-development workflow, with
> focused failing tests before implementation and independent review afterward.

**Goal:** Make executable declarations own tool capability truth and the full
compute-to-card contract without building a financial calculation.

**Architecture:** Neutral transport models stay separate from the catalog. The
catalog derives tool schemas from typed callables and owns policy and card
projection. Existing graph, message CAS, and frontend renderers consume those
facts; no second runtime or question classifier is introduced.

**Tech stack:** Python 3.10, Pydantic 2, LangGraph/LangChain, FastAPI, Next.js,
TypeScript, Bun, pytest and Vitest/Playwright.

**Spec:** `docs/superpowers/specs/2026-09-09-tool-registry.md`.

## Global constraints

No production calculator, universal input schema, question-shape mapping,
prototype promotion, state class relocation/rename, provider spend before
cost announcement, merge, deploy, hosted migration or sharing flag activation.
Keep every worker's files separate; report required ownership changes before
editing them. Workers do not commit or change other workers' files.

## Shared interfaces

- `domain/tool_contracts.py`: `ToolCall(tool_name, call_id, arguments)`,
  `ToolOutcome(status, result, failure)`, `ToolProgress(locale_key,
  interpolation_args, call_id, tool_name)`, `LocalizedText(locale_key,
  interpolation_args)`, `ToolFact(name, label, value, unit, value_text)`,
  `ToolInputFact(..., editable, unknown, visibility='private')`,
  `ToolCardPresentation(title, answer, rows, inputs, notes, narrative, sources,
  visual)`, `ToolResultCard(kind='tool_result', schema_version=1,
  tool_name, call_id, artifact_id, input_revision, card_type, card_version,
  arguments, outcome, presentation, artifact_state='active')`.
- `domain/tool_declaration.py`: `ToolDeclaration(name, description, handler,
  policy, progress, card, rules, domain)`; first handler parameter is a typed
  Pydantic argument model, its return annotation is a typed Pydantic result.
  An optional keyword-only `context` parameter is runtime-injected.
  `validate_arguments(arguments)`, `tool_schema()`, `progress_facts(arguments,
  call_id=...)`, and async `invoke(arguments, context=None)` are derived.
- `ToolPolicy(execution='local'|'workflow'|'provider', external_calls,
  confirmation='never'|'required', editable_fields=(), retain_unknown=True)`;
  `ToolProgressTemplate(locale_key, argument_fields)`;
  `ExactlyOneUnknown(fields)`; `ToolCardBinding(card_type, version, presenter)`.
  Presenter receives `(arguments, outcome)` and returns `ToolCardPresentation`.
- `capability_registry.py`: `get_tool_catalog()` returns an immutable
  `ToolCatalog` with declaration lookup, ordered schemas, and generated
  capability text. Built-in handler imports are deferred. Test code can inject
  a catalog of test-only typed callables.
- `FinalResponsePayload.tool_result_cards` is plural. Never put a non-backtest
  under legacy `result_card`: its publication branch persists a backtest.
- Required confirmation binds a real typed `confirmation_handler`; policy never
  substitutes for approval. Persisted asynchronous bindings use the complete
  catalog for completion even if new admission is later disabled. Per-call jobs
  and effects remain ordered rather than replacing one singular sidecar.
- The receipt sanitizer removes narrative and inputs with private visibility;
  shareable numeric assumptions, typed token translations, sources and the
  existing typed visual remain in the shared card contract. Its backtest
  projection derives the existing canonical fact builders.
- Generated fingerprint capture measures catalog/schema/rendered prompt across
  explicit research and execution-realism profiles with a fixed clock. The live
  harness must traverse the registered dispatch leg rather than stopping at the
  former interpret-to-confirm topology.

## Task 1: Declaration and neutral contracts (root)

Files: new `domain/tool_contracts.py`, `domain/tool_declaration.py`; modify
`domain/capability_registry.py`; new focused domain tests.

- [x] Test signature/schema derivation, bad declarations, cross-field null
  cardinality, zero preservation, typed returns and failures.
- [x] Implement only the declared contracts and derived methods.
- [x] Test policy validation, typed progress interpolation, immutable catalog,
  card version/type binding, and import independence in fresh processes.
- [x] Register built-in real handlers supplied by runtime/research workers.

## Task 2: Interpreter and research (interpreter worker)

Files: `llm_interpreter_types.py`, `state/models.py`, `stages/interpret_types.py`,
interpreter modules, `stages/interpret.py`, research modules and focused tests.

- [x] Add failing schema/route cases for four intents, zero/two/repeated calls,
  tool arguments not inheriting strategy fields, and unsupported strategy
  admission remaining scoped to strategies.
- [x] Generate specialized model-facing call schemas from catalog declarations;
  transport calls without classifying questions or running strategy repair on
  unrelated tools. Convert legacy intent values at persisted read boundaries.
- [x] Register the existing five research execution classes with typed real
  handlers; preserve provider pricing/cache/admission/source boundaries.
- [x] Generate capability answers and text from catalog data; remove primary
  question-kind dispatch ownership and hand-maintained capability lists.

## Task 3: Runtime execution and progress (runtime worker)

Files: `graph/workflow.py`, `stages/execute.py`, new `stages/tool_execution.py`,
`runtime.py`, `substage_events.py`, backtest adapter and focused tests.

- [x] Make `_launch_payload` raise in a cheap-tool test and prove execution
  succeeds without reaching it; prove expensive tools require confirmation.
- [x] Execute ordered calls in existing graph; preserve distinct call IDs and
  typed outcome/card records, including failures and multiple results.
- [x] Emit declaration-derived progress immediately around the actual call,
  and expose it through the existing live event channel.
- [x] Adapt actual backtest execution to a declaration without bypassing
  confirmation, durable admission, retry or launch validation.

## Task 4: Publication, revisions and receipts (persistence worker)

Files: API publication/recompute adapter and router, public-excerpt schema and
projection, message metadata and focused lifecycle/receipt tests.

- [x] Prove plural tool cards persist/reload without creating backtest runs.
- [x] Recompute through existing guarded message writer; test retained unknown,
  forbidden edit, stale revision before compute, racing stale write and no
  stale checkpoint projection.
- [x] Bind receipt v2 to sanitized shared presentation and retain v1 reads.
  Test ownership, privacy, failure/ambiguous-result handling and bilingual facts.

## Task 5: Shared UI (presentation worker)

Files: tool-card parser/renderer, live/reload message projection, status and API
transport, receipt presentation, locales and focused frontend/browser tests.

- [x] Prove answer-first card, blank vs zero, field edits/recompute and stale
  revision handling with backend-shaped fixtures.
- [x] Route live and hydrated plural cards through one parser and renderer.
- [x] Remove stage-keyed progress copy; localize actual-call templates with
  typed facts. Render receipts from shared presentation.
- [ ] Capture durable en/es-419 browser screenshots for changed surfaces.

## Task 6: Evidence and completion (root, verification support)

- [x] Migrate only stale Lane C lifecycle probe, preserve historical raw file,
  run all 31 probes and shared-loop import tests.
- [x] Run focused and mocked suites, lint, types and full runtime sweep;
  classify pre-existing failures against integration.
- [ ] Include generated catalog/schema in fingerprint measurement. Commit a
  clean candidate, run the announced full live gate, commit scorecard and
  fingerprint, investigate regressions without silently deleting cases.
- [ ] Reconcile latest integration, audit semantic overlap and merged-tree
  modularity, then publish non-draft PR with requested labels.
- [ ] Complete Codex review at exact head, resolve all threads, and wait for
  required terminal CI. Write final audit only after the review returns.
