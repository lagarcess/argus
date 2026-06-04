# Private Alpha Reliability Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Make the existing Argus chat/backtest runtime reliable enough for scheduled private-alpha internet testing on Render Free/Hobby without a broad rearchitecture.

**Architecture:** Keep the current app/API split, FastAPI chat stream, LangGraph runtime, Supabase product persistence, and Render manual deploy model. Add a small operations layer around the existing runtime: product readiness, provider-cache warmup, canary smoke automation, and durable failure breadcrumbs so Render restarts and broken golden paths are detected before human testers hit them.

**Tech Stack:** FastAPI, LangGraph, Supabase Postgres/Auth, Render web services, Bash/curl, Python stdlib JSON parsing, pytest.

---

## Evidence Snapshot

- Two deployed chat attempts saved the user message but produced no assistant message, no backtest run, and no route receipts.
- Render API logs showed `POST /api/v1/chat/stream` returned `200`, then the process restarted before route `finally` persistence ran.
- Render memory around the failed turns jumped from roughly 359 MB to 392 MB, then dropped to a cold-process baseline, consistent with restart.
- Current `.github/warmup-render.sh` only polls API `/health` and frontend `/`.
- A live warmup at `2026-06-04T15:50:04Z` needed six failed API `/health` attempts before the API responded, then two failed frontend attempts before the frontend responded.
- `src/argus/domain/market_data/assets.py` loads the live asset universe synchronously through Alpaca/Kraken when the cache is cold or expired.
- `MARKET_DATA_CACHE_TTL` defaults to 900 seconds, so a scheduled tester session can cross the TTL and make a live chat turn pay the cold provider-cache cost.
- `execute_stage_async()` already offloads execution with `asyncio.to_thread`; interpret-stage provider resolution still reaches synchronous `resolve_asset()` helpers.

## Non-Goals

- Do not add a queue, worker service, scheduler, Redis, Celery, RQ, Dramatiq, or Render paid-plan dependency.
- Do not create a second chat runtime or legacy orchestrator.
- Do not add regex/phrase gates before LLM interpretation.
- Do not add PostHog, Sentry, Datadog, or a new observability vendor in this slice.
- Do not delete or clean live Supabase data.
- Do not expose backend secrets in frontend env vars or committed config.

## File Structure

- Modify `src/argus/domain/market_data/assets.py`
  - Add a typed warmup/check function around the existing asset cache.
  - Keep all provider-catalog ownership in the market-data module.
- Modify `src/argus/domain/market_data/__init__.py`
  - Export the warmup/check function for API readiness use.
- Create `src/argus/api/routers/ops.py`
  - Add internal readiness endpoint and auth guard.
  - Keep `src/argus/api/main.py` thin.
- Modify `src/argus/api/main.py`
  - Include the ops router.
- Modify `src/argus/domain/supabase_gateway.py`
  - Add one small read-only health query helper.
- Modify `src/argus/api/routers/agent.py`
  - Persist a lightweight turn-start breadcrumb before entering risky runtime work.
  - Preserve existing stream behavior and user-facing contract.
- Modify `.github/warmup-render.sh`
  - Poll `/health`, frontend `/`, and the new readiness endpoint.
- Create `.github/canary-render.sh`
  - Run a real authenticated golden-path canary against the deployed URLs.
- Modify `render.yaml`
  - Add safe runtime configuration for longer provider-cache TTL.
  - Declare any new ops token as `sync: false`.
- Modify `docs/PRIVATE_LAUNCH_RUNBOOK.md`
  - Replace manual-only smoke instructions with warmup plus canary gates.
- Add `tests/test_private_alpha_readiness.py`
  - Cover readiness auth, readiness checks, and no-secret response shape.
- Add `tests/test_render_canary_script.py`
  - Cover script defaults, required env vars, no secret echoing, and golden-path assertions.
- Extend `tests/test_environment_scripts.py`
  - Ensure warmup script calls readiness, not just `/health`.
- Extend `tests/test_chat_stream_contract.py`
  - Ensure turn-start breadcrumbs are persisted before runtime failure.

---

### Task 1: Add Readiness Contract Tests

**Files:**
- Create: `tests/test_private_alpha_readiness.py`
- Modify: none

- [x] **Step 1: Write failing tests for disabled/unauthorized readiness**

```python
from __future__ import annotations

from fastapi.testclient import TestClient

from argus.api.main import app


def test_internal_readiness_is_404_when_ops_token_missing(
    monkeypatch,
) -> None:
    monkeypatch.delenv("ARGUS_OPS_TOKEN", raising=False)
    client = TestClient(app)

    response = client.get("/internal/readiness")

    assert response.status_code == 404


def test_internal_readiness_requires_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("ARGUS_OPS_TOKEN", "test-token")
    client = TestClient(app)

    response = client.get("/internal/readiness")

    assert response.status_code == 404
```

- [x] **Step 2: Write failing test for safe readiness response shape**

```python
def test_internal_readiness_returns_safe_check_summary(monkeypatch) -> None:
    from argus.api.routers import ops

    monkeypatch.setenv("ARGUS_OPS_TOKEN", "test-token")
    monkeypatch.setattr(
        ops,
        "run_readiness_checks",
        lambda request, force: {
            "status": "ready",
            "checks": [
                {"name": "supabase", "status": "ready", "duration_ms": 3},
                {"name": "asset_universe", "status": "ready", "duration_ms": 12},
            ],
        },
    )
    client = TestClient(app)

    response = client.get(
        "/internal/readiness",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["checks"][0]["name"] == "supabase"
    assert "SUPABASE_SERVICE_ROLE_KEY" not in response.text
    assert "OPENROUTER_API_KEY" not in response.text
    assert "ALPACA_SECRET_KEY" not in response.text
```

- [x] **Step 3: Run test to verify it fails**

Run:

```bash
poetry run pytest tests/test_private_alpha_readiness.py -q
```

Expected:

```text
FAILED ... 404 != 200
```

---

### Task 2: Implement Asset Warmup And Readiness Router

**Files:**
- Modify: `src/argus/domain/market_data/assets.py`
- Modify: `src/argus/domain/market_data/__init__.py`
- Modify: `src/argus/domain/supabase_gateway.py`
- Create: `src/argus/api/routers/ops.py`
- Modify: `src/argus/api/main.py`

- [x] **Step 1: Add asset warmup result types**

Add to `src/argus/domain/market_data/assets.py`:

```python
@dataclass(frozen=True)
class AssetUniverseWarmupResult:
    status: Literal["ready", "degraded"]
    provider_mode: AssetProviderMode
    alias_count: int
    required_symbols: tuple[str, ...]
    resolved_symbols: tuple[str, ...]
    missing_symbols: tuple[str, ...]
    duration_ms: int
```

- [x] **Step 2: Add the warmup function**

Add to `src/argus/domain/market_data/assets.py`:

```python
def warm_asset_universe(
    *,
    required_symbols: tuple[str, ...] = ("AAPL", "MSFT", "SPY"),
    force: bool = False,
) -> AssetUniverseWarmupResult:
    started = time.perf_counter()
    _refresh_asset_cache_if_needed(force=force)
    assert _ASSET_ALIAS_MAP is not None

    resolved: list[str] = []
    missing: list[str] = []
    for symbol in required_symbols:
        try:
            resolved.append(resolve_asset(symbol).canonical_symbol)
        except Exception:
            missing.append(symbol)

    duration_ms = int((time.perf_counter() - started) * 1000)
    return AssetUniverseWarmupResult(
        status="ready" if not missing else "degraded",
        provider_mode=_asset_provider_mode(),
        alias_count=len(_ASSET_ALIAS_MAP),
        required_symbols=required_symbols,
        resolved_symbols=tuple(resolved),
        missing_symbols=tuple(missing),
        duration_ms=duration_ms,
    )
```

- [x] **Step 3: Export warmup from market-data package**

Update `src/argus/domain/market_data/__init__.py`:

```python
from .assets import AssetUniverseWarmupResult, warm_asset_universe

__all__ = [
    "AssetUniverseWarmupResult",
    "warm_asset_universe",
    # keep existing exports here
]
```

- [x] **Step 4: Add Supabase health helper**

Add to `src/argus/domain/supabase_gateway.py`:

```python
def health_check(self) -> dict[str, Any]:
    started = time.perf_counter()
    self.client.table("profiles").select("id").limit(1).execute()
    return {
        "status": "ready",
        "duration_ms": int((time.perf_counter() - started) * 1000),
    }
```

Also add `import time` at the top of the file if absent.

- [x] **Step 5: Add ops readiness router**

Create `src/argus/api/routers/ops.py`:

```python
from __future__ import annotations

import asyncio
import hmac
import os
import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from argus.api import state as api_state
from argus.domain.market_data import warm_asset_universe

router = APIRouter(tags=["ops"])


def _ops_token() -> str:
    return (os.getenv("ARGUS_OPS_TOKEN") or "").strip()


def _require_ops_token(authorization: str | None) -> None:
    expected = _ops_token()
    if not expected:
        raise HTTPException(status_code=404, detail="Not found")
    expected_header = f"Bearer {expected}"
    if authorization is None or not hmac.compare_digest(authorization, expected_header):
        raise HTTPException(status_code=404, detail="Not found")


def _check(name: str, status: str, duration_ms: int, **extra: Any) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "duration_ms": duration_ms,
        **extra,
    }


async def run_readiness_checks(request: Request, *, force: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    started = time.perf_counter()
    workflow_ready = getattr(request.app.state, "agent_runtime_workflow", None) is not None
    checks.append(
        _check(
            "agent_runtime_workflow",
            "ready" if workflow_ready else "degraded",
            int((time.perf_counter() - started) * 1000),
        )
    )

    started = time.perf_counter()
    if api_state.supabase_gateway is None:
        checks.append(_check("supabase", "degraded", 0, reason="gateway_unavailable"))
    else:
        try:
            result = await asyncio.to_thread(api_state.supabase_gateway.health_check)
            checks.append(_check("supabase", result["status"], result["duration_ms"]))
        except Exception:
            checks.append(
                _check(
                    "supabase",
                    "degraded",
                    int((time.perf_counter() - started) * 1000),
                )
            )

    started = time.perf_counter()
    try:
        asset_result = await asyncio.wait_for(
            asyncio.to_thread(warm_asset_universe, force=force),
            timeout=float(os.getenv("ARGUS_READINESS_ASSET_TIMEOUT_SECONDS", "25")),
        )
        checks.append(
            _check(
                "asset_universe",
                asset_result.status,
                asset_result.duration_ms,
                provider_mode=asset_result.provider_mode,
                alias_count=asset_result.alias_count,
                required_symbols=list(asset_result.required_symbols),
                resolved_symbols=list(asset_result.resolved_symbols),
                missing_symbols=list(asset_result.missing_symbols),
            )
        )
    except Exception:
        checks.append(
            _check(
                "asset_universe",
                "degraded",
                int((time.perf_counter() - started) * 1000),
            )
        )

    status = "ready" if all(check["status"] == "ready" for check in checks) else "degraded"
    return {"status": status, "checks": checks}


@router.get("/internal/readiness")
async def readiness(
    request: Request,
    authorization: str | None = Header(default=None),
    force: bool = False,
) -> dict[str, Any]:
    _require_ops_token(authorization)
    return await run_readiness_checks(request, force=force)
```

- [x] **Step 6: Include the ops router**

Update `src/argus/api/main.py` imports and router registration:

```python
from argus.api.routers import ops

for api_router in (
    # existing routers
    ops.router,
):
    app.include_router(api_router)
```

- [x] **Step 7: Run readiness tests**

Run:

```bash
poetry run pytest tests/test_private_alpha_readiness.py -q
```

Expected:

```text
3 passed
```

---

### Task 3: Make Warmup Product-Aware

**Files:**
- Modify: `.github/warmup-render.sh`
- Modify: `tests/test_environment_scripts.py`
- Modify: `render.yaml`

- [x] **Step 1: Add failing environment-script assertion**

Extend `tests/test_environment_scripts.py`:

```python
def test_warmup_script_checks_product_readiness_endpoint() -> None:
    warmup = _source(".github/warmup-render.sh")

    assert "/internal/readiness" in warmup
    assert "ARGUS_OPS_TOKEN" in warmup
    assert "Argus product path is ready for testers" in warmup
```

- [x] **Step 2: Update warmup script**

Change `.github/warmup-render.sh` so it:

```bash
OPS_TOKEN="${ARGUS_OPS_TOKEN:-}"

wait_for_url() {
  local label="$1"
  local url="$2"
  shift 2
  local attempt=1

  echo "Warming $label: $url"
  while true; do
    if curl -fsS --max-time 15 "$@" "$url" > /dev/null; then
      echo "OK: $label responded"
      return 0
    fi

    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "ERROR: $label did not respond within ${TIMEOUT_SECONDS}s"
      return 1
    fi

    echo "  waiting for $label... attempt $attempt"
    attempt=$((attempt + 1))
    sleep "$SLEEP_SECONDS"
  done
}

wait_for_readiness() {
  if [ -z "$OPS_TOKEN" ]; then
    echo "ARGUS_OPS_TOKEN is required for product readiness warmup."
    return 1
  fi

  wait_for_url \
    "product readiness" \
    "${API_URL}/internal/readiness?force=true" \
    -H "Authorization: Bearer ${OPS_TOKEN}"
}
```

Then call readiness after `/health` and before frontend:

```bash
wait_for_url "API health" "${API_URL}/health"
wait_for_readiness
wait_for_url "frontend" "$APP_URL"

echo "Argus product path is ready for testers."
```

Keep output from echoing token values.

- [x] **Step 3: Update Render configuration**

Add safe API env vars to `render.yaml`:

```yaml
      - key: MARKET_DATA_CACHE_TTL
        value: "43200"
      - key: ARGUS_READINESS_ASSET_TIMEOUT_SECONDS
        value: "25"
      - key: ARGUS_OPS_TOKEN
        sync: false
```

- [x] **Step 4: Run focused tests**

Run:

```bash
poetry run pytest tests/test_environment_scripts.py tests/test_private_alpha_readiness.py -q
```

Expected:

```text
passed
```

---

### Task 4: Add Golden-Path Canary Script

**Files:**
- Create: `.github/canary-render.sh`
- Create: `tests/test_render_canary_script.py`

- [x] **Step 1: Write failing canary script tests**

Create `tests/test_render_canary_script.py`:

```python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canary_defaults_to_private_launch_urls() -> None:
    source = _source(".github/canary-render.sh")

    assert "https://argus-app-suz5.onrender.com" in source
    assert "https://argus-ohr5.onrender.com" in source


def test_canary_requires_auth_inputs_without_echoing_password() -> None:
    source = _source(".github/canary-render.sh")

    assert "ARGUS_CANARY_EMAIL" in source
    assert "ARGUS_CANARY_PASSWORD" in source
    assert "ARGUS_CANARY_PASSWORD is required" in source
    assert "set -x" not in source


def test_canary_exercises_confirmation_and_run_backtest_action() -> None:
    source = _source(".github/canary-render.sh")

    assert "Test an equal-weight AAPL and MSFT strategy from 2025 to 2026 to date" in source
    assert '"type":"run_backtest"' in source
    assert "backtest_run" in source
    assert "route_receipts" in source
    assert "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY" in source
```

- [x] **Step 2: Create canary script**

Create `.github/canary-render.sh`:

```bash
#!/bin/bash
# Authenticated golden-path canary for the private-alpha Render deployment.

set -euo pipefail

APP_URL="${ARGUS_CANARY_APP_URL:-https://argus-app-suz5.onrender.com}"
API_URL="${ARGUS_CANARY_API_URL:-https://argus-ohr5.onrender.com}"
EMAIL="${ARGUS_CANARY_EMAIL:-}"
PASSWORD="${ARGUS_CANARY_PASSWORD:-}"
SUPABASE_URL="${ARGUS_CANARY_SUPABASE_URL:-}"
SUPABASE_SERVICE_ROLE_KEY="${ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY:-}"
TIMEOUT_SECONDS="${ARGUS_CANARY_TIMEOUT_SECONDS:-240}"
PROMPT="${ARGUS_CANARY_PROMPT:-Test an equal-weight AAPL and MSFT strategy from 2025 to 2026 to date}"

if [ -z "$EMAIL" ]; then
  echo "ARGUS_CANARY_EMAIL is required."
  exit 1
fi

if [ -z "$PASSWORD" ]; then
  echo "ARGUS_CANARY_PASSWORD is required."
  exit 1
fi

COOKIE_JAR="$(mktemp)"
CONFIRMATION_STREAM="$(mktemp)"
RUN_STREAM="$(mktemp)"
trap 'rm -f "$COOKIE_JAR" "$CONFIRMATION_STREAM" "$RUN_STREAM"' EXIT

.github/warmup-render.sh

echo "Logging in canary user: $EMAIL"
LOGIN_BODY="$(
  CANARY_EMAIL="$EMAIL" CANARY_PASSWORD="$PASSWORD" python3 - <<'PY'
import json
import os

print(json.dumps({
    "email": os.environ["CANARY_EMAIL"],
    "password": os.environ["CANARY_PASSWORD"],
}))
PY
)"

curl -fsS \
  -c "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "$LOGIN_BODY" \
  "${API_URL}/api/v1/auth/login" >/dev/null

CONVERSATION_ID="$(
  curl -fsS \
    -b "$COOKIE_JAR" \
    -H "Content-Type: application/json" \
    -d "{}" \
    "${API_URL}/api/v1/conversations" |
  python3 -c 'import json,sys; print(json.load(sys.stdin)["conversation"]["id"])'
)"

echo "Created canary conversation: $CONVERSATION_ID"
curl -fsS -N \
  --max-time "$TIMEOUT_SECONDS" \
  -b "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\":\"$CONVERSATION_ID\",\"message\":\"$PROMPT\",\"language\":\"en\"}" \
  "${API_URL}/api/v1/chat/stream" > "$CONFIRMATION_STREAM"

python3 - "$CONFIRMATION_STREAM" <<'PY'
import json
import pathlib
import sys

stream = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
events = []
for part in stream.split("\n\n"):
    for line in part.splitlines():
        if line.startswith("data: "):
            raw = line.removeprefix("data: ").strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))
if "data: [DONE]" not in stream:
    raise SystemExit("confirmation stream did not finish")
if any(event.get("type") == "error" for event in events):
    raise SystemExit("confirmation stream returned error")
if not any(event.get("type") == "final" and event.get("payload", {}).get("confirmation") for event in events):
    raise SystemExit("confirmation stream did not return a confirmation")
PY

curl -fsS -N \
  --max-time "$TIMEOUT_SECONDS" \
  -b "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -d "{\"conversation_id\":\"$CONVERSATION_ID\",\"action\":{\"type\":\"run_backtest\",\"label\":\"Run backtest\",\"presentation\":\"confirmation\",\"payload\":{}},\"language\":\"en\"}" \
  "${API_URL}/api/v1/chat/stream" > "$RUN_STREAM"

python3 - "$RUN_STREAM" <<'PY'
import json
import pathlib
import sys

stream = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
events = []
for part in stream.split("\n\n"):
    for line in part.splitlines():
        if line.startswith("data: "):
            raw = line.removeprefix("data: ").strip()
            if raw and raw != "[DONE]":
                events.append(json.loads(raw))
if "data: [DONE]" not in stream:
    raise SystemExit("run stream did not finish")
if any(event.get("type") == "error" for event in events):
    raise SystemExit("run stream returned error")
finals = [event.get("payload", {}) for event in events if event.get("type") == "final"]
if not finals:
    raise SystemExit("run stream did not return final payload")
if not any(payload.get("run") for payload in finals):
    raise SystemExit("run stream did not persist a backtest_run")
PY

MESSAGES_JSON="$(
  curl -fsS -b "$COOKIE_JAR" \
    "${API_URL}/api/v1/conversations/${CONVERSATION_ID}/messages"
)"

python3 - <<'PY' "$MESSAGES_JSON"
import json
import sys

payload = json.loads(sys.argv[1])
roles = [item.get("role") for item in payload.get("items", [])]
if roles.count("user") < 1 or roles.count("assistant") < 2:
    raise SystemExit("conversation did not persist expected user and assistant messages")
PY

if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
  BACKTEST_ROWS="$(
    curl -fsS \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      "${SUPABASE_URL}/rest/v1/backtest_runs?select=id&conversation_id=eq.${CONVERSATION_ID}&limit=1"
  )"
  RECEIPT_ROWS="$(
    curl -fsS \
      -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
      -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}" \
      "${SUPABASE_URL}/rest/v1/route_receipts?select=id&conversation_id=eq.${CONVERSATION_ID}&limit=1"
  )"
  python3 - <<'PY' "$BACKTEST_ROWS" "$RECEIPT_ROWS"
import json
import sys

backtest_rows = json.loads(sys.argv[1])
receipt_rows = json.loads(sys.argv[2])
if not backtest_rows:
    raise SystemExit("Supabase verifier did not find canary backtest_run")
if not receipt_rows:
    raise SystemExit("Supabase verifier did not find canary route_receipts")
PY
else
  echo "Skipping Supabase verifier; set ARGUS_CANARY_SUPABASE_URL and ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY to verify DB rows."
fi

echo "Canary passed: confirmation, run_backtest action, backtest_run, and messages are present."
```

- [x] **Step 3: Run script tests**

Run:

```bash
poetry run pytest tests/test_render_canary_script.py -q
```

Expected:

```text
3 passed
```

---

### Task 5: Persist Turn-Start Breadcrumbs Before Runtime Risk

**Files:**
- Modify: `src/argus/api/routers/agent.py`
- Modify: `tests/test_chat_stream_contract.py`

- [x] **Step 1: Write failing breadcrumb test**

Add to `tests/test_chat_stream_contract.py`:

```python
def test_chat_stream_persists_turn_start_receipt_before_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from argus.api.routers import agent as agent_router

    async def _crashing_stream_agent_turn_events(**_: Any):
        raise RuntimeError("runtime died before first event")
        yield {"type": "final", "payload": {}}

    monkeypatch.setattr(
        agent_router,
        "stream_agent_turn_events",
        _crashing_stream_agent_turn_events,
    )
    client = _client()
    conversation = _conversation(client)

    response = client.post(
        "/api/v1/chat/stream",
        json={
            "conversation_id": conversation["id"],
            "message": "Test AAPL and MSFT",
            "language": "en",
        },
    )

    assert response.status_code == 200
    messages = client.get(f"/api/v1/conversations/{conversation['id']}/messages").json()[
        "items"
    ]
    assistant = messages[-1]
    assert assistant["metadata"]["agent_runtime_stage_outcome"] == "agent_runtime_failure"
```

This test proves caught failures still persist recovery. The production restart case is outside Python's control, so the implementation must also create an early marker before `stream_agent_turn_events()`.

- [x] **Step 2: Add early runtime-start metadata**

In `src/argus/api/routers/agent.py`, before `begin_openrouter_route_receipt_capture()`:

```python
turn_started_at = datetime.now(timezone.utc).isoformat()
receipt_metadata = {
    "stage_outcome": "agent_runtime_started",
    "conversation_mode": "runtime",
    "turn_started_at": turn_started_at,
}
```

If `route_receipts` cannot represent non-LLM breadcrumbs, do not invent fake OpenRouter receipts. Instead persist this marker as metadata on the user message created for the turn.

- [x] **Step 3: Keep route receipts truthful**

Ensure `persist_route_receipts()` still only persists real OpenRouter receipts and that synthetic operational markers do not pollute `route_receipts.task` with fake model calls.

- [x] **Step 4: Run stream contract tests**

Run:

```bash
poetry run pytest tests/test_chat_stream_contract.py -q
```

Expected:

```text
passed
```

---

### Task 6: Update Runbook And Verification Gates

**Files:**
- Modify: `docs/PRIVATE_LAUNCH_RUNBOOK.md`

- [x] **Step 1: Replace warmup-only guidance**

Update "Before Tester Sessions" to require:

6. Export local ops/canary secrets:

```bash
export ARGUS_OPS_TOKEN="..."
export ARGUS_CANARY_EMAIL="..."
export ARGUS_CANARY_PASSWORD="..."
export ARGUS_CANARY_SUPABASE_URL="https://lgdhvepyrzbnscqssgqq.supabase.co"
export ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY="..."
```

7. Run product warmup:

```bash
.github/warmup-render.sh
```

8. Run the golden-path canary:

```bash
.github/canary-render.sh
```

Only send the app URL to testers after both scripts pass.

- [x] **Step 2: Add Render env reminder**

Document:

```markdown
Set `ARGUS_OPS_TOKEN` manually in Render for `argus-api`; it is intentionally `sync: false`.
Keep `ARGUS_OPS_TOKEN` out of frontend env vars.
```

- [x] **Step 3: Add failure interpretation**

Document:

```markdown
If warmup fails, do not invite testers yet. Check Render service status and redeploy only if the service is stuck.
If warmup passes but canary fails, treat it as an Argus product-path regression and inspect API logs, Supabase messages, backtest_runs, and route_receipts for the canary conversation id.
```

---

## Verification Commands

Run locally before PR:

```bash
poetry run pytest tests/test_private_alpha_readiness.py tests/test_render_canary_script.py tests/test_environment_scripts.py tests/test_chat_stream_contract.py -q
poetry run ruff check src tests
```

Run against deployed Render after merge and manual deploy:

```bash
export ARGUS_OPS_TOKEN="..."
export ARGUS_CANARY_EMAIL="..."
export ARGUS_CANARY_PASSWORD="..."
.github/warmup-render.sh
.github/canary-render.sh
```

Production acceptance:

- API `/health` responds.
- `/internal/readiness?force=true` returns `status: ready`.
- Canary first turn returns a confirmation.
- Canary second turn executes `run_backtest`.
- Canary stream includes `[DONE]`.
- Supabase persists user and assistant messages for the canary conversation.
- Supabase persists a `backtest_runs` row for the canary conversation.
- Route receipts exist for the canary conversation.
- Render API does not restart during the canary window.

## Rollback

- Revert the PR commit.
- Remove `ARGUS_OPS_TOKEN` from Render if the ops endpoint is removed.
- Keep `MARKET_DATA_CACHE_TTL` at the previous value only if provider freshness becomes more important than scheduled-session stability.
