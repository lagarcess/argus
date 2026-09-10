# Four-artifact extension audit

This read-only extension trace uses a hypothetical local scalar echo, not a
financial calculation. It identifies the edits a new operation needs; it is
not a live-measurement or readiness claim.

1. **Declaration and registration.** Add the declaration to
   `domain/capability_registry.py:get_tool_catalog`, naming its real handler,
   local/zero-external-call/never-confirm policy, editable input facts,
   `public_receipt="typed_facts"`, progress key and versioned card presenter.
   Catalog inclusion is part of this declaration artifact.
2. **Callable and typed models.** Define `echo(EchoArguments) -> EchoResult`.
   Its annotations supply the argument and return contracts. The catalog
   generates the model-facing call schema and capability text from them.
3. **Tests.** Cover typed validation, known zero, declared failure outcomes,
   repeated calls, recompute/reload and selected-turn publication. Existing
   echo/identity fixtures exercise these shared seams without adding a
   production calculation.
4. **Card and locale copy.** Supply `ToolCardPresentation` with answer and input
   facts, plus English/Spanish keys. The same chat presentation and receipt
   renderer consume those facts; no per-tool form or public body is needed.

The traced consumers are generated response types in
`agent_runtime/llm_interpreter_types.py`, declaration dispatch in
`agent_runtime/stages/tool_execution.py`, the guarded recompute route in
`api/routers/tool_results.py`, and the shared chat/public card renderers. No
additional intent enum, question classifier, router branch, input form or
receipt-body edit is required for this echo.

The bounded claim is independent calls with known typed arguments. Zero calls
execute nothing; up to `MAX_TOOL_CALLS` ordered calls support different and
repeated tools with distinct call ids. This does not claim result-reference
chaining between calls. The existing editor accepts scalar inputs and preserves
a declared unknown. Recompute requires the latest active message. Sharing
keeps sibling cards within one selected turn and freezes their source revisions;
every sibling must pass its declaration's public-receipt policy.

The audit required no edits to production, provider calls or new processes.
The receipt consumer's reconciliation tests, full live scorecard and final
review remain separate acceptance obligations.
