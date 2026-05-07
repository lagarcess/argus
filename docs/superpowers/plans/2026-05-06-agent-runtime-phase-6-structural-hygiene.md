# Agent Runtime Phase 6 Structural Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose `src/argus/api/main.py` into focused routers and shared dependencies, then delete or finish purging legacy runtime artifacts so the LangGraph runtime is the only active chat/backtest path.

**Architecture:** Keep FastAPI as a thin entry point: app creation, middleware, lifespan, exception handler, and router registration only. Move route handlers into `src/argus/api/routers/`, move shared request/auth/problem/cursor/state helpers into focused support modules, and preserve the current API contract and mock auth behavior while deleting `src/argus/domain/orchestrator.py`.

**Tech Stack:** FastAPI, Pydantic, Supabase gateway, LangGraph checkpointers, pytest `TestClient`, Poetry.

---

## Source Of Truth Read Before Planning

- `docs/PRODUCT.md`
- `docs/ARCHITECTURE.md`
- `docs/API_CONTRACT.md`
- `docs/DATA_MODEL.md`
- `.agent/designs/argus/DESIGN.md`
- `temp/argus_runtime_sot.md`, especially Part VII.

Current branch verified before planning: `fix/argus-runtime-sot`.

## File Structure

Create:
- `src/argus/api/dependencies.py` - `current_user()`, `problem()`, request-id middleware helpers, auth/session helpers, mock-auth fallback guard.
- `src/argus/api/state.py` - process-local `AlphaStore`, optional `SupabaseGateway`, runtime workflow construction, runtime workflow reset helpers.
- `src/argus/api/pagination.py` - cursor encode/decode, invalid cursor problem helper.
- `src/argus/api/naming.py` - starter prompts and LLM-backed entity-name suggestion moved out of deleted orchestrator.
- `src/argus/api/message_store.py` - memory and Supabase message/conversation persistence helpers used by conversation and agent routers.
- `src/argus/api/backtest_service.py` - direct backtest validation/execution/persistence helpers currently embedded in `main.py`.
- `src/argus/api/chat_service.py` - SSE formatting, onboarding control parsing, runtime result card/envelope helpers, result-action helpers.
- `src/argus/api/routers/__init__.py` - router package marker and optional exported router list.
- `src/argus/api/routers/auth.py` - `/api/v1/auth/session`, `/api/v1/auth/signup`, `/api/v1/auth/login`, `/api/v1/auth/logout`.
- `src/argus/api/routers/profile.py` - `/api/v1/me` GET/PATCH.
- `src/argus/api/routers/conversations.py` - `/api/v1/conversations` CRUD and `/messages`.
- `src/argus/api/routers/strategies.py` - `/api/v1/strategies` CRUD.
- `src/argus/api/routers/collections.py` - `/api/v1/collections` CRUD and strategy attach/detach.
- `src/argus/api/routers/backtest.py` - `/api/v1/backtests/run` and `/api/v1/backtests/{run_id}`.
- `src/argus/api/routers/agent.py` - `/internal/agent-runtime/turn` and `/api/v1/chat/stream`.
- `src/argus/api/routers/history.py` - `/api/v1/history`.
- `src/argus/api/routers/search.py` - `/api/v1/search`.
- `src/argus/api/routers/discovery.py` - `/api/v1/discovery/assets`, `/api/v1/discovery/indicators`.
- `src/argus/api/routers/feedback.py` - `/api/v1/feedback`.
- `src/argus/api/routers/dev.py` - `/api/v1/dev/reset`.
- `tests/test_phase6_api_structure.py` - structural guardrails for router extraction and legacy deletion.

Modify:
- `src/argus/api/main.py` - slim to app setup, middleware, exception handler, health endpoint if kept local, and router registration.
- `src/argus/agent_runtime/extraction/structured.py` - keep only `detect_unsupported_constraints()`; verify no regex NLU or extraction fallback remains.
- `src/argus/agent_runtime/signals/task_relation.py` - keep only `resolve_response_profile_overrides()`; verify no regex NLU or symbol dictionaries remain.
- `tests/test_alpha_api.py` - update monkeypatch targets from `argus.api.main` to the extracted modules.
- `tests/test_alpha_api_supabase.py` - update gateway/runtime monkeypatch targets and login test credentials.
- `tests/test_chat_backtest_state_machine.py` - update store/runtime helper imports.
- `tests/test_chat_runtime_cutover.py` - update confirmation-card helper imports.
- `tests/test_cursor_encoding.py` - import cursor helpers from `argus.api.pagination`.
- `tests/test_runtime_confirmation_card.py` - import confirmation-card helper from `argus.api.chat_service`.
- `tests/test_openrouter_policy.py` - import result-breakdown helper from `argus.api.chat_service`.
- `tests/test_conversational_ux.py` - assert deleted orchestrator module is unavailable instead of importing it.
- `tests/test_strategy_capabilities.py` - assert aliases live in registry without importing deleted orchestrator.
- `tests/test_legacy_orchestrator_retirement.py` - assert `src/argus/domain/orchestrator.py` is deleted.

Delete:
- `src/argus/domain/orchestrator.py`

Do not modify:
- No Phase 7 context-aware provenance/amnesia fixes.
- No new agent behavior, prompts, features, endpoint shapes, or frontend changes.
- No changes to backtest math or strategy semantics except moving existing code.

---

### Task 1: Add Structural Guard Tests First

**Files:**
- Create: `tests/test_phase6_api_structure.py`

- [ ] **Step 1: Write failing structural tests**

Add:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_api_main_is_only_app_entrypoint() -> None:
    source = _source("src/argus/api/main.py")

    assert "include_router(" in source
    assert "from argus.api.routers import" in source
    assert "@app.post(\"/api/v1/chat/stream\")" not in source
    assert "@app.post(\"/api/v1/backtests/run\")" not in source
    assert "@app.post(\"/api/v1/strategies\")" not in source
    assert "@app.post(\"/api/v1/collections\")" not in source
    assert "@app.post(\"/api/v1/conversations\")" not in source
    assert "from argus.domain.orchestrator" not in source
    assert len(source.splitlines()) <= 180


def test_required_api_router_modules_exist() -> None:
    required = [
        "auth",
        "profile",
        "conversations",
        "strategies",
        "collections",
        "backtest",
        "agent",
        "history",
        "search",
        "discovery",
        "feedback",
        "dev",
    ]
    for name in required:
        path = ROOT / "src" / "argus" / "api" / "routers" / f"{name}.py"
        assert path.exists(), f"missing router {name}"
        assert f"router = APIRouter(" in path.read_text(encoding="utf-8")


def test_shared_dependencies_are_not_in_main() -> None:
    main = _source("src/argus/api/main.py")
    dependencies = _source("src/argus/api/dependencies.py")

    assert "def current_user" not in main
    assert "def problem" not in main
    assert "def current_user" in dependencies
    assert "def problem" in dependencies


def test_legacy_orchestrator_file_is_deleted() -> None:
    assert not (ROOT / "src" / "argus" / "domain" / "orchestrator.py").exists()
    assert importlib.util.find_spec("argus.domain.orchestrator") is None


def test_regex_nlu_artifacts_are_absent() -> None:
    paths = [
        "src/argus/agent_runtime/stages/interpret.py",
        "src/argus/agent_runtime/extraction/structured.py",
        "src/argus/agent_runtime/signals/task_relation.py",
    ]
    forbidden = [
        "extract_signals(",
        "extract_strategy_fields(",
        "detect_symbols(",
        "extract_date_range(",
        "explicit_strategy_logic_present(",
        "_is_approval_message(",
        "_confirmation_edit_action(",
        "_social_opener_response(",
        "SYMBOL_ALIASES",
        "COMMON_NAMES",
        "NON_SYMBOLS",
    ]
    combined = "\n".join(_source(path) for path in paths)
    for token in forbidden:
        assert token not in combined
```

- [ ] **Step 2: Run the structural test and verify it fails before implementation**

Run:

```bash
poetry run pytest tests/test_phase6_api_structure.py -q --no-cov
```

Expected: FAIL because `api/main.py` still owns route handlers and `src/argus/domain/orchestrator.py` still exists.

---

### Task 2: Extract Shared State, Dependencies, Pagination, And Naming

**Files:**
- Create: `src/argus/api/state.py`
- Create: `src/argus/api/dependencies.py`
- Create: `src/argus/api/pagination.py`
- Create: `src/argus/api/naming.py`
- Modify: `src/argus/api/main.py`

- [ ] **Step 1: Move process state and runtime workflow wiring into `api/state.py`**

Move these existing concepts out of `main.py` with unchanged behavior:

```python
load_dotenv()
PERSISTENCE_MODE = os.getenv("ARGUS_PERSISTENCE_MODE", "memory").strip().lower()
agent_runtime_capability_contract = build_default_capability_contract()
store = AlphaStore()
supabase_gateway = SupabaseGateway.from_env() if PERSISTENCE_MODE == "supabase" else None


def build_agent_runtime_workflow(*, checkpointer: Any):
    ...


def get_agent_runtime_workflow(request: Request):
    ...


def reset_agent_runtime_workflow(app: FastAPI) -> None:
    checkpointer = MemorySaver()
    app.state.agent_runtime_checkpointer = checkpointer
    app.state.agent_runtime_workflow = build_agent_runtime_workflow(
        checkpointer=checkpointer
    )
```

Keep the MemorySaver fallback so tests using `TestClient(app)` still work without a lifespan-created workflow.

- [ ] **Step 2: Move `problem()` and `current_user()` into `api/dependencies.py`**

Preserve the existing mock-auth branch exactly:

```python
def current_user(request: Request) -> User:
    if (
        os.getenv("NEXT_PUBLIC_MOCK_AUTH", "").strip().lower() == "true"
        or os.getenv("ARGUS_MOCK_AUTH", "").strip().lower() == "true"
    ):
        if api_state.supabase_gateway is not None:
            try:
                return api_state.supabase_gateway.get_or_create_mock_user()
            except Exception:
                pass
        return api_state.store.get_or_create_dev_user()
    ...
```

Keep bearer-token and `sb-auth-token` cookie extraction behavior unchanged.

- [ ] **Step 3: Move cursor helpers into `api/pagination.py`**

Move:

```python
def encode_cursor(timestamp: str, id: str) -> str: ...
def decode_cursor(cursor: str, request: Request) -> tuple[str, str]: ...
def invalid_cursor_problem(request: Request) -> HTTPException: ...
```

Then update tests to import `encode_cursor` and `decode_cursor` from `argus.api.pagination`.

- [ ] **Step 4: Move starter prompts and entity naming into `api/naming.py`**

Move the non-routing helpers from `domain/orchestrator.py` into `api/naming.py`:

```python
SUPPORTED_GOALS = {...}
STARTER_PROMPTS = {...}

class NameSuggestion(BaseModel):
    name: str

def get_starter_prompts(primary_goal: str | None) -> list[str]: ...
def suggest_entity_name(*, entity_type: Literal["conversation", "strategy", "collection"], context: str, language: str | None) -> str | None: ...
```

No route or runtime module may import `argus.domain.orchestrator` after this step.

- [ ] **Step 5: Run the focused helper tests**

Run:

```bash
poetry run pytest tests/test_cursor_encoding.py tests/test_legacy_orchestrator_retirement.py tests/test_strategy_capabilities.py -q --no-cov
```

Expected after this task: cursor imports pass; orchestrator deletion test may still fail until Task 6 deletes the file.

---

### Task 3: Extract Message, Backtest, And Chat Support Services

**Files:**
- Create: `src/argus/api/message_store.py`
- Create: `src/argus/api/backtest_service.py`
- Create: `src/argus/api/chat_service.py`
- Modify: `src/argus/api/main.py`

- [ ] **Step 1: Move message persistence helpers into `message_store.py`**

Move unchanged behavior for:

```python
def dev_memory_fallback_enabled() -> bool: ...
def memory_conversation(*, title: str, title_source: str, language: str | None) -> Conversation: ...
def memory_message(*, conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> Message: ...
def message_preview(content: str, max_length: int = 180) -> str | None: ...
def create_message(*, user_id: str, conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> Message: ...
def load_runtime_thread_history(*, user_id: str, conversation_id: str, limit: int = 20) -> list[ConversationMessage]: ...
```

Every function should read `api_state.store` and `api_state.supabase_gateway`.

- [ ] **Step 2: Move direct backtest helpers into `backtest_service.py`**

Move unchanged behavior for:

```python
def raise_backtest_problem(request: Request, code: str, context: dict[str, Any] | None = None) -> None: ...
def ensure_same_asset_or_raise(symbols: list[str], requested_asset_class: str | None, request: Request) -> tuple[str, list[ResolvedAsset]]: ...
def create_run_from_payload(*, user: User, payload: dict[str, Any], request: Request, persist_in_memory: bool = True) -> BacktestRun: ...
```

Keep same-asset, stablecoin, timeframe, long-only, parameters, lookback, and provider-window errors byte-for-byte where possible.

- [ ] **Step 3: Move chat/runtime helpers into `chat_service.py`**

Move unchanged behavior for:

```python
def sse(event: str, payload: dict[str, Any]) -> str: ...
def sse_data(payload: dict[str, Any]) -> str: ...
def sse_done() -> str: ...
def parse_onboarding_control_message(message: str) -> str | None: ...
def runtime_confirmation_card(runtime_result: dict[str, Any]) -> dict[str, Any] | None: ...
def runtime_result_card(runtime_result: dict[str, Any]) -> dict[str, Any] | None: ...
def runtime_result_envelope(runtime_result: dict[str, Any]) -> dict[str, Any]: ...
def persist_runtime_backtest_run(*, user: User, conversation: Conversation, result_card: dict[str, Any], envelope: dict[str, Any]) -> BacktestRun | None: ...
def llm_result_breakdown_message(context: dict[str, Any]) -> str | None: ...
def result_breakdown_message(run: BacktestRun | None) -> str: ...
```

Tests currently importing `_runtime_confirmation_card` and `_llm_result_breakdown_message` from `main.py` must switch to `argus.api.chat_service`.

- [ ] **Step 4: Run chat helper tests**

Run:

```bash
poetry run pytest tests/test_runtime_confirmation_card.py tests/test_openrouter_policy.py -q --no-cov
```

Expected: PASS after test imports are updated and helper behavior is preserved.

---

### Task 4: Extract Core Contract Routers

**Files:**
- Create: `src/argus/api/routers/auth.py`
- Create: `src/argus/api/routers/profile.py`
- Create: `src/argus/api/routers/conversations.py`
- Create: `src/argus/api/routers/strategies.py`
- Create: `src/argus/api/routers/collections.py`
- Create: `src/argus/api/routers/backtest.py`
- Create: `src/argus/api/routers/__init__.py`
- Modify: `src/argus/api/main.py`

- [ ] **Step 1: Extract auth/profile routes**

Use this router shape:

```python
from fastapi import APIRouter, Depends, Request

router = APIRouter(prefix="/api/v1", tags=["auth"])
```

Move:
- `GET /auth/session`
- `POST /auth/signup`
- `POST /auth/login`
- `POST /auth/logout`

Use `MOCK_USER_EMAIL` and `MOCK_USER_PASSWORD` in login-flow tests, not hard-coded developer credentials:

```python
email = os.environ.get("MOCK_USER_EMAIL", "developer@argus.local")
password = os.environ.get("MOCK_USER_PASSWORD", "password")
```

Create a separate profile router for:
- `GET /me`
- `PATCH /me`

- [ ] **Step 2: Extract conversations router**

Move unchanged behavior for:
- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `PATCH /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations/{conversation_id}`
- `GET /api/v1/conversations/{conversation_id}/messages`

Use `current_user`, `problem`, `decode_cursor`, `encode_cursor`, `message_store.memory_conversation`, and `api_state.store`.

- [ ] **Step 3: Extract strategies and collections routers**

Move unchanged behavior for:
- `POST /api/v1/strategies`
- `GET /api/v1/strategies`
- `PATCH /api/v1/strategies/{strategy_id}`
- `DELETE /api/v1/strategies/{strategy_id}`
- `POST /api/v1/collections`
- `GET /api/v1/collections`
- `PATCH /api/v1/collections/{collection_id}`
- `DELETE /api/v1/collections/{collection_id}`
- `POST /api/v1/collections/{collection_id}/strategies`
- `DELETE /api/v1/collections/{collection_id}/strategies/{strategy_id}`

Use `api.naming.suggest_entity_name()` for generated names.

- [ ] **Step 4: Extract backtest router**

Move unchanged behavior for:
- `POST /api/v1/backtests/run`
- `GET /api/v1/backtests/{run_id}`

Keep idempotency key behavior and Supabase quota increments unchanged.

- [ ] **Step 5: Run core API tests**

Run:

```bash
poetry run pytest tests/test_alpha_api.py tests/test_alpha_api_supabase.py -q --no-cov
```

Expected: PASS after monkeypatch targets are updated to `argus.api.state`, `argus.api.routers.agent`, and `argus.api.chat_service`.

---

### Task 5: Extract Agent, History, Search, Discovery, Feedback, And Dev Routers

**Files:**
- Create: `src/argus/api/routers/agent.py`
- Create: `src/argus/api/routers/history.py`
- Create: `src/argus/api/routers/search.py`
- Create: `src/argus/api/routers/discovery.py`
- Create: `src/argus/api/routers/feedback.py`
- Create: `src/argus/api/routers/dev.py`
- Modify: `src/argus/api/main.py`

- [ ] **Step 1: Extract agent routes**

Move:
- `POST /internal/agent-runtime/turn`
- `POST /api/v1/chat/stream`

Keep `/api/v1/chat/stream` as the public contract endpoint. Use `stream_agent_turn_events()` and `api_state.get_agent_runtime_workflow(request)` exactly as the active runtime entry point. Do not introduce a new `/api/v1/conversations/{id}/chat` route in Phase 6.

- [ ] **Step 2: Extract history/search/discovery/feedback/dev routes**

Move unchanged behavior for:
- `GET /api/v1/history`
- `GET /api/v1/search`
- `GET /api/v1/chat/starter-prompts`
- `GET /api/v1/discovery/assets`
- `GET /api/v1/discovery/indicators`
- `POST /api/v1/feedback`
- `POST /api/v1/dev/reset`

`/api/v1/dev/reset` must reset `api_state.store` and the app runtime workflow through `api_state.reset_agent_runtime_workflow(request.app)`.

- [ ] **Step 3: Run conversational/runtime API tests**

Run:

```bash
poetry run pytest tests/test_chat_runtime_cutover.py tests/test_chat_backtest_state_machine.py tests/test_conversational_ux.py -q --no-cov
```

Expected: PASS after imports and monkeypatch targets are updated.

---

### Task 6: Slim `api/main.py` And Delete Legacy Artifacts

**Files:**
- Modify: `src/argus/api/main.py`
- Delete: `src/argus/domain/orchestrator.py`
- Modify: `src/argus/agent_runtime/extraction/structured.py`
- Modify: `src/argus/agent_runtime/signals/task_relation.py`
- Modify: `tests/test_legacy_orchestrator_retirement.py`

- [ ] **Step 1: Rewrite `api/main.py` as the app entry point**

Target shape:

```python
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import MemorySaver

from argus.api import state as api_state
from argus.api.dependencies import problem, request_id_middleware
from argus.api.routers import (
    agent,
    auth,
    backtest,
    collections,
    conversations,
    dev,
    discovery,
    feedback,
    history,
    profile,
    search,
    strategies,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ...


app = FastAPI(title="Argus Alpha API", version="1.0.0-alpha", lifespan=lifespan)
app.middleware("http")(request_id_middleware)
app.add_middleware(CORSMiddleware, ...)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    ...


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


for router in (...):
    app.include_router(router.router)
```

Keep `store = api_state.store` as a read-only compatibility alias only if needed by tests; all routers must use `api_state.store` directly.

- [ ] **Step 2: Delete `src/argus/domain/orchestrator.py`**

Use `apply_patch` delete. Then verify no import remains:

```bash
rg -n "domain\\.orchestrator|argus\\.domain\\.orchestrator|from argus.domain.orchestrator" src tests
```

Expected: no matches.

- [ ] **Step 3: Finish NLU cleanup verification**

`structured.py` should contain only deterministic unsupported-constraint validation:

```python
def detect_unsupported_constraints(
    *,
    strategy: StrategySummary,
    contract: CapabilityContract,
) -> list[UnsupportedConstraint]:
    ...
```

`task_relation.py` should contain only:

```python
def resolve_response_profile_overrides(_: str) -> ResponseProfileOverrides:
    return ResponseProfileOverrides()
```

No regex imports, symbol dictionaries, extraction helpers, or intent classifiers should remain.

- [ ] **Step 4: Run structural guard tests**

Run:

```bash
poetry run pytest tests/test_phase6_api_structure.py tests/test_legacy_orchestrator_retirement.py tests/agent_runtime/test_interpret_stage.py -q --no-cov
```

Expected: PASS.

---

### Task 7: Smoke Test Standard CRUD And Mock Auth Guard

**Files:**
- No production files.
- Optional temporary script: `temp/phase6_smoke.py` during execution only.

- [ ] **Step 1: Run memory-mode smoke through `TestClient`**

Use this script content if a temporary smoke script is useful:

```python
from __future__ import annotations

import os

from fastapi.testclient import TestClient

from argus.api.main import app

os.environ["NEXT_PUBLIC_MOCK_AUTH"] = "true"

client = TestClient(app)

assert client.post("/api/v1/dev/reset").status_code == 200

session = client.get("/api/v1/auth/session")
assert session.status_code == 200, session.text
assert session.json()["authenticated"] is True

conversation = client.post("/api/v1/conversations", json={"title": "Phase 6 smoke"})
assert conversation.status_code == 200, conversation.text

strategy = client.post(
    "/api/v1/strategies",
    json={
        "name": "TSLA smoke",
        "template": "rsi_mean_reversion",
        "asset_class": "equity",
        "symbols": ["TSLA"],
        "parameters": {},
    },
)
assert strategy.status_code == 200, strategy.text

listed = client.get("/api/v1/conversations")
assert listed.status_code == 200, listed.text
assert listed.json()["items"]
```

Run:

```bash
$env:NEXT_PUBLIC_MOCK_AUTH='true'; poetry run python temp/phase6_smoke.py
```

Expected: command exits 0.

- [ ] **Step 2: Run login-flow smoke with canonical mock credentials**

Use mocked Supabase gateway tests for deterministic login behavior:

```bash
$env:MOCK_USER_EMAIL=$env:MOCK_USER_EMAIL; $env:MOCK_USER_PASSWORD=$env:MOCK_USER_PASSWORD; poetry run pytest tests/test_alpha_api_supabase.py::test_login_sets_session_cookie_for_browser_auth -q --no-cov
```

Expected: PASS and `sb-auth-token` / `sb-refresh-token` cookies are set.

---

### Task 8: Full Verification And Self Review

**Files:**
- No production files unless failures identify missed mechanical moves.

- [ ] **Step 1: Run import/format/lint checks**

Run:

```bash
poetry run ruff check src/argus/api src/argus/agent_runtime/extraction/structured.py src/argus/agent_runtime/signals/task_relation.py tests/test_phase6_api_structure.py --no-cache
```

Expected: PASS.

- [ ] **Step 2: Run targeted backend suite**

Run:

```bash
poetry run pytest tests/test_phase6_api_structure.py tests/test_alpha_api.py tests/test_alpha_api_supabase.py tests/test_chat_runtime_cutover.py tests/test_chat_backtest_state_machine.py tests/test_legacy_orchestrator_retirement.py tests/agent_runtime/test_interpret_stage.py -q --no-cov
```

Expected: PASS.

- [ ] **Step 3: Run full backend suite if targeted suite passes**

Run:

```bash
poetry run pytest -q --no-cov
```

Expected: PASS, or report unrelated pre-existing failures with exact failing test names and errors.

- [ ] **Step 4: Run self review**

Review checklist:
- `api/main.py` has no business logic and is near the target size.
- Every previous route is still registered.
- `NEXT_PUBLIC_MOCK_AUTH=true` still returns the mock developer user without Supabase.
- `/api/v1/auth/login` still sets browser auth cookies when a Supabase gateway returns a session.
- `/api/v1/chat/stream` still emits `stage_start`, `stage_outcome`, `token`, `final`, and `[DONE]` events.
- `src/argus/domain/orchestrator.py` is deleted.
- No `domain.orchestrator` imports remain.
- No regex NLU, symbol alias dictionaries, or intent-classification helpers remain in `interpret.py`, `structured.py`, or `task_relation.py`.
- No context-aware provenance or new agent feature work slipped into the diff.

---

## Approval Gate

Stop here before implementation. Execute this plan only after explicit approval for Phase 6 code changes.
