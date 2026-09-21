# Assistant and frontend seam review

Reviewed the frozen assistant backend, contracts, interpreter admission boundary, `features/assistant/**`, focused tests, and `docs/platform-api/assistant.md` against `money-view/docs/PLATFORM_PLAN.md`. The initial review found two P2 boundary failures. This scoped re-review inspected only their fixes and the admitted `ModelLease.call_timeout_seconds` fixture adjustment.

**Spec compliance: pass. Code quality: pass.** Both original findings are resolved, and no new P1/P2 issue was found in the fix delta.

## Resolved findings

### Invalid conversations no longer reach memory, model, or financial work

- `money-view/server/platform/assistant.py:354-366` makes `_active_conversation` the shared household and active-state owner.
- `answer_question` validates an existing target before `grounded_facts` at `assistant.py:485-486`, then rechecks under the write lock at `assistant.py:497-500`. Prepared requests therefore fail before canonical financial reads, while the locked check prevents a concurrent archive from receiving a new turn.
- The semantic route validates the target in the thread pool before loading confirmed memories or calling the model at `assistant.py:730-747`. A missing, foreign-household, archived, or trashed target now causes the documented 404 or 409 without external disclosure or allowance consumption.
- `money-view/tests/test_platform_assistant.py:894-936` covers all eight input-kind and invalid-target combinations and forbids memory, model, and fact work. The concurrent archive case at `test_platform_assistant.py:939-966` proves that the recheck leaves the original answer history unchanged.

### Assistant export now shares session-expiry handling

- `money-view/web/src/features/assistant/AssistantDrawer.tsx:3,51` routes the blob download through `requestResponse`.
- `money-view/web/src/platform/client.ts:13-43` is the single response boundary; it dispatches `clara:session-expired` for `401 authentication_required` before throwing the typed API error.
- `money-view/web/e2e/assistant-export.spec.ts:3-16` exercises the actual drawer flow with loaded facts, forces an export 401, and verifies that login replaces the authenticated UI and removes the drawer and answers.

## Verification evidence

The implementer reports 60 focused assistant and interpreter backend tests passing, including the eight invalid-target cases and concurrent archive guard; the assistant export browser case passed against the real UI and shared client in 3.5 seconds; and `bun run build` passed. Those checks were not rerun during this read-only re-review. The typed `ModelLease` test fixtures now supply `call_timeout_seconds`; the adjustment matches the runtime lease contract and introduces no behavioral fork.

The previously verified grounding, immutable receipts, household and user scoping, lifecycle operations, bounded pagination and exports, keyless and HTTP fail-closed behavior, shared model admission, event-loop boundaries, and auth-switch response invalidation remain unchanged by this fix delta.

No provider/model calls, Git operations, server starts, environment changes, or application edits were performed. Only this review report was updated. Review complete; no active follow-up retained.
