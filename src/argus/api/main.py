from __future__ import annotations

import base64
import binascii
import json
import os
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.runtime import run_agent_turn
from argus.agent_runtime.session.manager import InMemorySessionManager
from argus.agent_runtime.state.models import UserState
from argus.agent_runtime.strategy_contract import (
    display_strategy_slug,
    display_strategy_type,
    executable_strategy_type,
    resolve_date_range,
)
from argus.agent_runtime.tools.real_backtest import RealBacktestTool
from argus.api.schemas import (
    BacktestRun,
    BacktestRunRequest,
    BacktestRunResponse,
    ChatStreamRequest,
    Collection,
    CollectionAttach,
    CollectionCreate,
    CollectionPatch,
    CollectionResponse,
    Conversation,
    ConversationCreate,
    ConversationPatch,
    ConversationResponse,
    FeedbackRequest,
    HistoryItem,
    LoginRequest,
    Message,
    PaginatedCollections,
    PaginatedConversations,
    PaginatedHistory,
    PaginatedMessages,
    PaginatedSearch,
    PaginatedStrategies,
    ProfilePatch,
    SearchItem,
    SignupRequest,
    StarterPromptsResponse,
    Strategy,
    StrategyCreate,
    StrategyPatch,
    StrategyResponse,
    SuccessResponse,
    User,
    UserResponse,
)
from argus.domain.backtest_state_machine import (
    BacktestConversationState,
)
from argus.domain.engine import (
    build_result_card,
    classify_symbol,
    compute_alpha_metrics,
    default_benchmark,
    normalize_backtest_config,
    validate_backtest_config,
)
from argus.domain.orchestrator import (
    get_starter_prompts,
    parse_onboarding_goal,
    suggest_entity_name,
)
from argus.domain.store import AlphaStore, utcnow
from argus.domain.supabase_gateway import QuotaExceededError, SupabaseGateway

load_dotenv()

app = FastAPI(title="Argus Alpha API", version="1.0.0-alpha")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
store = AlphaStore()
PERSISTENCE_MODE = os.getenv("ARGUS_PERSISTENCE_MODE", "memory").strip().lower()
supabase_gateway = SupabaseGateway.from_env() if PERSISTENCE_MODE == "supabase" else None
agent_runtime_session_manager = InMemorySessionManager()
agent_runtime_capability_contract = build_default_capability_contract()
agent_runtime_workflow = build_workflow(
    contract=agent_runtime_capability_contract,
    tool=RealBacktestTool(),
    structured_interpreter=OpenRouterStructuredInterpreter(
        contract=agent_runtime_capability_contract,
    ),
)


class InternalAgentRuntimeTurnRequest(BaseModel):
    user_id: str
    thread_id: str
    message: str


def _dev_memory_fallback_enabled() -> bool:
    return (
        os.getenv("NEXT_PUBLIC_MOCK_AUTH", "").strip().lower() == "true"
        and os.getenv("ARGUS_SUPABASE_STRICT", "").strip().lower() != "true"
    )


def _memory_conversation(
    *,
    title: str,
    title_source: str,
    language: str | None,
) -> Conversation:
    now = utcnow()
    conversation = Conversation(
        id=store.new_id(),
        title=title,
        title_source=title_source,
        language=language,
        created_at=now,
        updated_at=now,
    )
    store.conversations[conversation.id] = conversation
    store.messages[conversation.id] = []
    return conversation


def _memory_message(
    *, conversation_id: str, role: str, content: str, metadata: dict[str, Any] | None = None
) -> Message:
    message = Message(
        id=store.new_id(),
        conversation_id=conversation_id,
        role=role,
        content=content,
        created_at=utcnow(),
        metadata=metadata,
    )
    store.messages.setdefault(conversation_id, []).append(message)
    return message


def _create_message(
    *,
    user_id: str,
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    if supabase_gateway is not None:
        try:
            return supabase_gateway.create_message(
                user_id=user_id,
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata=metadata,
            )
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase message write failed; using dev memory fallback",
                error=str(exc),
                conversation_id=conversation_id,
            )
    return _memory_message(
        conversation_id=conversation_id, role=role, content=content, metadata=metadata
    )


def _latest_backtest_state(
    history: list[dict[str, Any]],
) -> BacktestConversationState:
    for message in reversed(history):
        metadata = message.get("metadata") or {}
        raw_state = metadata.get("backtest_state")
        if not raw_state and metadata.get("conversation_mode") == "guide":
            return BacktestConversationState()
        if raw_state:
            try:
                return BacktestConversationState.model_validate(raw_state)
            except Exception as exc:
                logger.warning("Backtest state rehydration failed", error=str(exc))
                return BacktestConversationState()
    return BacktestConversationState()


def _state_has_params(state: BacktestConversationState) -> bool:
    params = state.params
    return bool(
        params.template
        or params.symbols
        or params.asset_class
        or params.timeframe
        or params.start_date
        or params.end_date
        or params.starting_capital
        or params.parameters
    )


def _latest_completed_run_id(history: list[dict[str, Any]]) -> str | None:
    for message in reversed(history):
        metadata = message.get("metadata") or {}
        run_id = metadata.get("latest_run_id")
        if run_id:
            return str(run_id)
    return None


def _fetch_run_metrics(user_id: str, run_id: str) -> dict[str, Any] | None:
    """Fetch actual metrics and config from a completed backtest run."""
    run = None
    if supabase_gateway is not None:
        try:
            run = supabase_gateway.get_backtest_run(user_id=user_id, run_id=run_id)
        except Exception as exc:
            logger.warning(
                "Failed to fetch run for result explanation",
                error=str(exc),
                run_id=run_id,
            )
    if run is None:
        run = store.backtest_runs.get(run_id)
    if run is None:
        return None
    return {
        "aggregate": run.metrics.get("aggregate", {}),
        "by_symbol": run.metrics.get("by_symbol", {}),
        "config": run.config_snapshot,
    }


def _assistant_copy_for_result(symbols: list[str], language: str) -> str:
    joined = ", ".join(symbols)
    if language.startswith("es"):
        return f"¡Listo! Aquí tienes los resultados del backtest para {joined}. ¿Qué te parecen estas métricas?"
    return f"Done! Here are the backtest results for {joined}. What do you think about these metrics?"


def _runtime_result_message(runtime_result: dict[str, Any]) -> str | None:
    assistant_response = runtime_result.get("assistant_response")
    if isinstance(assistant_response, str) and assistant_response:
        return assistant_response
    assistant_prompt = runtime_result.get("assistant_prompt")
    if isinstance(assistant_prompt, str) and assistant_prompt:
        return assistant_prompt
    return None


def _runtime_stage_status(runtime_result: dict[str, Any]) -> str:
    stage_outcome = runtime_result.get("stage_outcome")
    if isinstance(stage_outcome, str) and stage_outcome:
        return stage_outcome
    return "agent_runtime_turn"


def _runtime_result_card(runtime_result: dict[str, Any]) -> dict[str, Any] | None:
    final_payload = runtime_result.get("final_response_payload")
    if not isinstance(final_payload, dict):
        return None
    result_card = final_payload.get("result_card")
    if isinstance(result_card, dict):
        return result_card
    return None


def _runtime_confirmation_card(runtime_result: dict[str, Any]) -> dict[str, Any] | None:
    if runtime_result.get("stage_outcome") != "await_approval":
        return None
    payload = runtime_result.get("confirmation_payload")
    if not isinstance(payload, dict):
        return None
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    optional_parameters = payload.get("optional_parameters")
    if not isinstance(optional_parameters, dict):
        optional_parameters = {}

    symbols = [
        str(symbol)
        for symbol in strategy.get("asset_universe", [])
        if str(symbol).strip()
    ]
    assets = ", ".join(symbols) if symbols else "Selected asset"
    strategy_type = display_strategy_slug(strategy)
    strategy_label = display_strategy_type(strategy)
    date_range = _format_confirmation_period(strategy.get("date_range"))
    title = f"{assets} {strategy_type}".strip()

    rows = [
        {"label": "Strategy", "value": strategy_label},
        {"label": "Assets", "value": assets},
        {"label": "Period", "value": date_range},
    ]
    canonical_strategy_type = executable_strategy_type(strategy)
    if strategy.get("cadence") and _strategy_type_uses_cadence(canonical_strategy_type):
        rows.append({"label": "Cadence", "value": str(strategy["cadence"]).title()})
    if strategy.get("entry_logic"):
        rows.append({"label": "Buy rule", "value": _format_confirmation_value(strategy["entry_logic"])})
    if strategy.get("exit_logic"):
        rows.append({"label": "Exit rule", "value": _format_confirmation_value(strategy["exit_logic"])})
    if strategy.get("capital_amount"):
        rows.append({"label": "Contribution", "value": f"${float(strategy['capital_amount']):,.0f}"})

    assumptions = _confirmation_assumptions(
        strategy=strategy,
        optional_parameters=optional_parameters,
    )
    summary = (
        f"I read this as {assets} using {_article_for(strategy_type)} "
        f"{strategy_type} approach over {date_range}."
    )
    return {
        "title": title,
        "statusLabel": "Ready to run",
        "summary": summary,
        "rows": rows,
        "assumptions": assumptions,
        "actions": [
            {"id": "run-backtest", "label": "Run backtest", "value": "Run backtest"},
            {"id": "change-dates", "label": "Change dates", "value": "Change the date range"},
            {"id": "change-asset", "label": "Change asset", "value": "Use a different asset"},
            {"id": "adjust-assumptions", "label": "Adjust assumptions", "value": "Change the assumptions"},
        ],
    }


def _confirmation_assumptions(
    *,
    strategy: dict[str, Any],
    optional_parameters: dict[str, Any],
) -> list[str]:
    assumptions: list[str] = []
    initial_capital = _optional_parameter_value(optional_parameters, "initial_capital")
    if isinstance(initial_capital, int | float):
        strategy_type = executable_strategy_type(strategy)
        if _strategy_type_uses_cadence(strategy_type) and strategy.get("capital_amount"):
            assumptions.append(f"${float(strategy['capital_amount']):,.0f} recurring contribution")
        else:
            assumptions.append(f"${float(initial_capital):,.0f} starting capital")
    timeframe = _optional_parameter_value(optional_parameters, "timeframe")
    if timeframe:
        assumptions.append(f"{timeframe} bars")
    fees = _optional_parameter_value(optional_parameters, "fees")
    if fees in (0, 0.0, "0", "0.0"):
        assumptions.append("No fees")
    slippage = _optional_parameter_value(optional_parameters, "slippage")
    if slippage in (0, 0.0, "0", "0.0"):
        assumptions.append("No slippage")
    asset_class = strategy.get("asset_class")
    if asset_class == "crypto":
        assumptions.append("Benchmark: BTC")
    elif asset_class == "equity":
        assumptions.append("Benchmark: SPY")
    return assumptions


def _optional_parameter_value(optional_parameters: dict[str, Any], key: str) -> Any:
    value = optional_parameters.get(key)
    if isinstance(value, dict):
        return value.get("value")
    return None


def _format_confirmation_value(value: Any) -> str:
    if isinstance(value, dict):
        start = value.get("start") or value.get("from")
        end = value.get("end") or value.get("to")
        if start and end:
            return f"{start} to {end}"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None or value == "":
        return "Default period"
    return str(value)


def _format_confirmation_period(value: Any) -> str:
    return resolve_date_range(value, today=_confirmation_today()).display


def _strategy_type_uses_cadence(strategy_type: str) -> bool:
    normalized = strategy_type.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {
        "dca",
        "dca_accumulation",
        "recurring_accumulation",
        "recurring_buys",
    }


def _article_for(value: str) -> str:
    return "an" if value[:1].lower() in {"a", "e", "i", "o", "u"} else "a"


def _confirmation_today() -> date:
    return date.today()


def _runtime_result_envelope(runtime_result: dict[str, Any]) -> dict[str, Any]:
    final_payload = runtime_result.get("final_response_payload")
    if not isinstance(final_payload, dict):
        return {}
    result = final_payload.get("result")
    return dict(result) if isinstance(result, dict) else {}


def _build_runtime_backtest_run(
    *,
    user_id: str,
    conversation_id: str,
    result_card: dict[str, Any],
    envelope: dict[str, Any],
) -> BacktestRun | None:
    resolved_strategy = envelope.get("resolved_strategy")
    resolved_parameters = envelope.get("resolved_parameters")
    metrics = envelope.get("metrics")
    benchmark_metrics = envelope.get("benchmark_metrics")
    if not isinstance(resolved_strategy, dict) or not isinstance(metrics, dict):
        return None

    symbol = resolved_strategy.get("symbol")
    if not isinstance(symbol, str) or not symbol:
        asset_universe = resolved_strategy.get("asset_universe")
        if isinstance(asset_universe, list) and asset_universe:
            symbol = str(asset_universe[0])
        elif isinstance(asset_universe, str) and asset_universe:
            symbol = asset_universe
        else:
            return None
    symbol = symbol.strip().upper()

    try:
        asset_class = classify_symbol(symbol).asset_class
    except ValueError:
        asset_class = "equity"

    benchmark_symbol = "BTC" if asset_class == "crypto" else "SPY"
    if isinstance(benchmark_metrics, dict):
        candidate_benchmark = benchmark_metrics.get("benchmark_symbol")
        if isinstance(candidate_benchmark, str) and candidate_benchmark:
            benchmark_symbol = candidate_benchmark.strip().upper()

    resolved_parameters_dict = (
        dict(resolved_parameters) if isinstance(resolved_parameters, dict) else {}
    )
    config_snapshot = {
        "template": resolved_strategy.get("strategy_type", "strategy"),
        "symbols": [symbol],
        "timeframe": resolved_parameters_dict.get("timeframe", "1D"),
        "date_range": resolved_parameters_dict.get("date_range"),
        "benchmark_symbol": benchmark_symbol,
        "resolved_strategy": resolved_strategy,
        "resolved_parameters": resolved_parameters_dict,
    }

    return BacktestRun(
        id=store.new_id(),
        conversation_id=conversation_id,
        strategy_id=None,
        status="completed",
        asset_class=asset_class,
        symbols=[symbol],
        allocation_method="equal_weight",
        benchmark_symbol=benchmark_symbol,
        metrics=metrics,
        config_snapshot=config_snapshot,
        conversation_result_card=result_card,
        created_at=utcnow(),
        chart=None,
        trades=[],
    )


def _persist_runtime_backtest_run(
    *,
    user: User,
    conversation: Conversation,
    result_card: dict[str, Any],
    envelope: dict[str, Any],
) -> BacktestRun | None:
    run = _build_runtime_backtest_run(
        user_id=user.id,
        conversation_id=conversation.id,
        result_card=result_card,
        envelope=envelope,
    )
    if run is None:
        return None

    store.backtest_runs[run.id] = run
    store.backtest_run_owners[run.id] = user.id

    if supabase_gateway is not None:
        try:
            supabase_gateway.create_backtest_run(user_id=user.id, run=run)
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase backtest run write failed; using dev memory fallback",
                error=str(exc),
                run_id=run.id,
            )

    if conversation.id in store.conversations:
        store.conversations[conversation.id] = conversation.model_copy(
            update={
                "last_message_preview": result_card.get("title") or conversation.last_message_preview,
                "updated_at": utcnow(),
            }
        )

    return run


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or store.new_id()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    response.headers.setdefault("X-RateLimit-Limit", "200")
    response.headers.setdefault("X-RateLimit-Remaining", "199")
    response.headers.setdefault("X-RateLimit-Reset", "3600")
    return response


def problem(
    request: Request,
    *,
    status_code: int,
    code: str,
    title: str,
    detail: str,
    context: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    body = {
        "type": f"https://api.argus.app/problems/{code.replace('_', '-')}",
        "title": title,
        "status": status_code,
        "detail": detail,
        "code": code,
        "request_id": request.state.request_id,
    }
    if context:
        body["context"] = context
    return HTTPException(status_code=status_code, detail=body, headers=headers)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):  # type: ignore[no-untyped-def]
    from fastapi.responses import JSONResponse

    if isinstance(exc.detail, dict) and "code" in exc.detail:
        body = exc.detail
    else:
        body = {
            "type": "https://api.argus.app/problems/http-error",
            "title": "Request Failed",
            "status": exc.status_code,
            "detail": str(exc.detail),
            "code": "http_error",
            "request_id": request.state.request_id,
        }

    origin = request.headers.get("origin")
    headers = dict(exc.headers or {})
    headers["Access-Control-Allow-Origin"] = origin or "*"
    if origin:
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(body, status_code=exc.status_code, headers=headers)


def _encode_cursor(timestamp: str, id: str) -> str:
    raw = f"{timestamp}|{id}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _invalid_cursor_problem(request: Request) -> HTTPException:
    return problem(
        request,
        status_code=400,
        code="validation_error",
        title="Validation Error",
        detail="Invalid cursor.",
    )


def _decode_cursor(cursor: str, request: Request) -> tuple[str, str]:
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        if "|" not in decoded:
            raise ValueError()
        timestamp, item_id = decoded.rsplit("|", 1)
        return timestamp, item_id
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise _invalid_cursor_problem(request) from None


def _search_type_rank(kind: str) -> int:
    ranks = {
        "chat": 4,
        "strategy": 3,
        "collection": 2,
        "run": 1,
    }
    return ranks.get(kind, 0)


def _score_search_item(
    *,
    query: str,
    title: str,
    matched_text: str,
    pinned: bool,
    symbol_exact_match: bool = False,
) -> int:
    score = 0
    if pinned:
        score += 1000
    lower_title = title.lower()
    lower_matched = matched_text.lower()
    if query == lower_title:
        score += 500
    elif query in lower_title:
        score += 100
    if query in lower_matched:
        score += 50
    if symbol_exact_match:
        score += 200
    return score


def _auth_response(request: Request, payload: dict[str, Any]) -> JSONResponse:
    response = JSONResponse(payload)
    session = payload.get("session")
    if not isinstance(session, dict):
        return response

    access_token = session.get("access_token")
    refresh_token = session.get("refresh_token")
    max_age = session.get("expires_in")
    cookie_kwargs: dict[str, Any] = {
        "httponly": True,
        "path": "/",
        "samesite": "lax",
        "secure": request.url.scheme == "https",
    }
    if isinstance(max_age, int):
        cookie_kwargs["max_age"] = max_age

    if isinstance(access_token, str) and access_token:
        response.set_cookie("sb-auth-token", access_token, **cookie_kwargs)
    if isinstance(refresh_token, str) and refresh_token:
        response.set_cookie("sb-refresh-token", refresh_token, **cookie_kwargs)
    return response


def current_user(request: Request) -> User:
    if (
        os.getenv("NEXT_PUBLIC_MOCK_AUTH", "").strip().lower() == "true"
        or os.getenv("ARGUS_MOCK_AUTH", "").strip().lower() == "true"
    ):
        user = store.get_or_create_dev_user()
        if supabase_gateway is not None:
            try:
                supabase_gateway.get_or_create_mock_user()
            except Exception:
                pass
        return user

    if supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for non-mock authentication.",
        )

    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ")
    else:
        potential_tokens = []
        for key, value in request.cookies.items():
            if key.startswith("sb-") and ("auth-token" in key or "access-token" in key):
                try:
                    clean_value = value.strip('"')
                    if clean_value.startswith("{") or clean_value.startswith("["):
                        token_data = json.loads(clean_value)
                        extracted = (
                            token_data.get("access_token")
                            if isinstance(token_data, dict)
                            else None
                        )
                        if extracted:
                            potential_tokens.append(extracted)
                    else:
                        potential_tokens.append(clean_value)
                except Exception:
                    potential_tokens.append(value)

        for t_val in potential_tokens:
            if t_val:
                token = t_val
                break

    if not token:
        raise problem(
            request,
            status_code=401,
            code="unauthorized",
            title="Unauthorized",
            detail="Missing or invalid Authorization header or session cookie.",
        )

    try:
        auth_user = supabase_gateway.get_auth_user_from_token(token)
    except Exception:
        raise problem(
            request,
            status_code=401,
            code="unauthorized",
            title="Unauthorized",
            detail="Invalid or expired access token.",
        ) from None

    return supabase_gateway.get_or_create_profile_for_auth_user(auth_user)


@app.post("/api/v1/dev/reset", response_model=SuccessResponse)
def dev_reset() -> SuccessResponse:
    store.reset()
    agent_runtime_session_manager._threads.clear()
    store.get_or_create_dev_user()
    return SuccessResponse(success=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "version": "1.0.0-alpha"}


@app.post("/internal/agent-runtime/turn")
def internal_agent_runtime_turn(
    payload: InternalAgentRuntimeTurnRequest,
) -> dict[str, Any]:
    return run_agent_turn(
        workflow=agent_runtime_workflow,
        session_manager=agent_runtime_session_manager,
        user=UserState(user_id=payload.user_id),
        thread_id=payload.thread_id,
        message=payload.message,
    )


@app.get("/api/v1/auth/session")
def auth_session(user: User = Depends(current_user)) -> dict[str, Any]:  # noqa: B008
    return {"authenticated": True, "user": user.model_dump(mode="json")}


@app.post("/api/v1/auth/signup")
def signup(request: Request, body: SignupRequest) -> JSONResponse:
    if supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for authentication.",
        )
    try:
        result = supabase_gateway.signup(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            username=body.username,
        )
        return _auth_response(request, result)
    except Exception as exc:
        raise problem(
            request,
            status_code=400,
            code="bad_request",
            title="Signup Failed",
            detail=str(exc),
        ) from exc


@app.post("/api/v1/auth/login")
def login(request: Request, body: LoginRequest) -> JSONResponse:
    if supabase_gateway is None:
        raise problem(
            request,
            status_code=500,
            code="internal_error",
            title="Internal Error",
            detail="Supabase persistence is required for authentication.",
        )
    try:
        result = supabase_gateway.login(email=body.email, password=body.password)
        return _auth_response(request, result)
    except Exception as exc:
        raise problem(
            request,
            status_code=401,
            code="unauthorized",
            title="Login Failed",
            detail=str(exc),
        ) from exc


@app.post("/api/v1/auth/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"success": True})
    response.delete_cookie("sb-auth-token", path="/")
    response.delete_cookie("sb-refresh-token", path="/")
    return response


@app.get("/api/v1/me", response_model=UserResponse)
def get_me(user: User = Depends(current_user)) -> UserResponse:  # noqa: B008
    if supabase_gateway is not None:
        try:
            prof = supabase_gateway.get_user(user_id=user.id)
            if prof:
                return UserResponse(user=prof)
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase profile read failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
            )
    return UserResponse(user=user)


@app.patch("/api/v1/me", response_model=UserResponse)
def patch_me(
    patch: ProfilePatch,
    user: User = Depends(current_user),  # noqa: B008
) -> UserResponse:
    current = (
        supabase_gateway.get_user(user_id=user.id)
        if supabase_gateway is not None
        else store.users.get(user.id, user)
    )
    if current is None:
        current = user

    data = current.model_dump()
    updates = patch.model_dump(exclude_unset=True)
    onboarding_patch = updates.pop("onboarding", None)
    data.update(updates)
    if onboarding_patch:
        onboarding = current.onboarding.model_dump()
        onboarding.update(onboarding_patch)
        data["onboarding"] = onboarding
    data["updated_at"] = utcnow()
    updated = User.model_validate(data)

    if supabase_gateway is not None:
        try:
            updated = supabase_gateway.update_user(
                user.id, updated.model_dump(mode="json")
            )
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase profile patch failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
            )
    store.users[user.id] = updated
    return UserResponse(user=updated)


@app.post("/api/v1/conversations", response_model=ConversationResponse)
def create_conversation(
    payload: ConversationCreate,
    user: User = Depends(current_user),  # noqa: B008
) -> ConversationResponse:
    title = payload.title or "New idea"
    if supabase_gateway is not None:
        try:
            conversation = supabase_gateway.create_conversation(
                user_id=user.id,
                title=title,
                title_source="user_renamed" if payload.title else "system_default",
                language=payload.language or user.language,
            )
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase conversation create failed; using dev memory fallback",
                error=str(exc),
            )
            conversation = _memory_conversation(
                title=title,
                title_source="user_renamed" if payload.title else "system_default",
                language=payload.language or user.language,
            )
    else:
        conversation = _memory_conversation(
            title=title,
            title_source="user_renamed" if payload.title else "system_default",
            language=payload.language or user.language,
        )
    return ConversationResponse(conversation=conversation)


@app.get("/api/v1/conversations", response_model=PaginatedConversations)
def list_conversations(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    archived: bool | None = Query(None),
    deleted: bool = Query(False),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedConversations:
    if supabase_gateway is not None:
        items = supabase_gateway.list_conversations(
            user_id=user.id, limit=None, archived=archived, deleted=deleted
        )
    else:
        items = []
        for conversation in store.conversations.values():
            # Filter by deleted status
            if deleted:
                if conversation.deleted_at is None:
                    continue
            else:
                if conversation.deleted_at is not None:
                    continue

            # Filter by archived status (if specified)
            if archived is not None:
                if conversation.archived != archived:
                    continue

            items.append(conversation)

    items.sort(
        key=lambda item: (int(item.pinned), item.updated_at, item.id), reverse=True
    )
    filtered = items
    if cursor:
        cursor_updated_at, cursor_id = _decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_updated_at)
        except ValueError:
            raise _invalid_cursor_problem(request) from None
        # Find the cursor item to get its pinned status, fallback to False if not found for strict tie breaking
        cursor_pinned = next(
            (item.pinned for item in items if item.id == cursor_id), False
        )
        cursor_key = (int(bool(cursor_pinned)), cursor_dt, cursor_id)
        filtered = [
            item
            for item in items
            if (int(item.pinned), item.updated_at, item.id) < cursor_key
        ]
    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = _encode_cursor(last.updated_at.isoformat(), last.id)
    return PaginatedConversations(items=page_items, next_cursor=next_cursor)


@app.patch("/api/v1/conversations/{conversation_id}", response_model=ConversationResponse)
def patch_conversation(
    conversation_id: str,
    payload: ConversationPatch,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
):
    conversation = (
        supabase_gateway.get_conversation(
            user_id=user.id, conversation_id=conversation_id
        )
        if supabase_gateway
        else store.conversations.get(conversation_id)
    )
    if not conversation:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )
    data = conversation.model_dump()
    patch = payload.model_dump(exclude_unset=True)
    if "title" in patch and patch["title"]:
        patch["title_source"] = "user_renamed"
    if supabase_gateway is not None:
        updated = supabase_gateway.patch_conversation(
            user_id=user.id, conversation_id=conversation_id, patch=patch
        )
        if not updated:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Conversation not found.",
            )
    else:
        data.update(patch)
        data["updated_at"] = utcnow()
        updated = Conversation.model_validate(data)
        store.conversations[conversation_id] = updated
    return ConversationResponse(conversation=updated)


@app.delete("/api/v1/conversations/{conversation_id}", response_model=SuccessResponse)
def delete_conversation(
    conversation_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
):
    conversation = (
        supabase_gateway.get_conversation(
            user_id=user.id, conversation_id=conversation_id
        )
        if supabase_gateway
        else store.conversations.get(conversation_id)
    )
    if not conversation:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )
    if supabase_gateway is not None:
        supabase_gateway.soft_delete_conversation(
            user_id=user.id, conversation_id=conversation_id
        )
    else:
        store.conversations[conversation_id] = conversation.model_copy(
            update={"deleted_at": utcnow(), "updated_at": utcnow()}
        )
    return SuccessResponse(success=True)


@app.get(
    "/api/v1/conversations/{conversation_id}/messages", response_model=PaginatedMessages
)
def list_messages(
    conversation_id: str,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(current_user),  # noqa: B008
):
    items: list[Message] | None = None
    if supabase_gateway is not None:
        try:
            items = supabase_gateway.list_messages(
                user_id=user.id, conversation_id=conversation_id, limit=None
            )
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase message list failed; using dev memory fallback",
                error=str(exc),
                conversation_id=conversation_id,
            )

    if items is None:
        conversation = store.conversations.get(conversation_id)
        if not conversation:
            return PaginatedMessages(items=[])
        items = store.messages.get(conversation_id, [])

    items.sort(key=lambda item: (item.created_at, item.id))
    filtered = items
    if cursor:
        cursor_created_at, cursor_id = _decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_created_at)
        except ValueError:
            raise _invalid_cursor_problem(request) from None
        cursor_key = (cursor_dt, cursor_id)
        filtered = [item for item in items if (item.created_at, item.id) > cursor_key]
    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = _encode_cursor(last.created_at.isoformat(), last.id)
    return PaginatedMessages(items=page_items, next_cursor=next_cursor)


def _raise_backtest_problem(
    request: Request, code: str, *, context: dict[str, Any] | None = None
) -> None:
    mapping: dict[str, tuple[int, str, str]] = {
        "invalid_symbol": (
            422,
            "Invalid Symbol",
            "One or more symbols are not supported in the active Alpaca asset universe.",
        ),
        "invalid_symbol_count": (
            422,
            "Invalid Symbol Count",
            "Alpha supports between 1 and 5 symbols per run.",
        ),
        "mixed_asset_not_supported": (
            422,
            "Mixed Asset Simulation Not Supported",
            "Alpha supports grouped symbols within the same asset class only.",
        ),
        "asset_class_conflict": (
            422,
            "Asset Class Conflict",
            "Requested asset_class does not match inferred symbol asset class.",
        ),
        "unsupported_template": (
            422,
            "Unsupported Strategy Template",
            "Template is not supported in Alpha.",
        ),
        "unsupported_timeframe": (
            422,
            "Unsupported Timeframe",
            "Supported timeframes are 1h, 2h, 4h, 6h, 12h, and 1D.",
        ),
        "unsupported_side": (
            422,
            "Unsupported Position Side",
            "Alpha supports long-only backtests.",
        ),
        "unsupported_allocation_method": (
            422,
            "Unsupported Allocation Method",
            "Alpha supports equal_weight allocation only.",
        ),
        "unsupported_parameters": (
            422,
            "Unsupported Parameters",
            "Indicator and risk parameter customization is not enabled for Alpha MVP templates.",
        ),
        "invalid_starting_capital": (
            422,
            "Invalid Starting Capital",
            "starting_capital must be between 1,000 and 100,000,000.",
        ),
        "invalid_date_range": (
            422,
            "Invalid Date Range",
            "start_date must be before end_date and end_date cannot be in the future.",
        ),
        "invalid_lookback_window": (
            422,
            "Invalid Lookback Window",
            "Alpha supports lookback windows up to 3 years.",
        ),
        "stablecoin_not_supported": (
            422,
            "Stablecoin Not Supported",
            "Stablecoins are excluded from Alpha backtesting.",
        ),
        "invalid_benchmark_symbol": (
            422,
            "Invalid Benchmark Symbol",
            "benchmark_symbol must match the run asset class.",
        ),
        "asset_universe_unavailable": (
            503,
            "Asset Universe Unavailable",
            "Asset validation is temporarily unavailable. Please retry shortly.",
        ),
        "market_data_unavailable": (
            503,
            "Market Data Unavailable",
            "Market data is temporarily unavailable. Please retry shortly.",
        ),
    }
    status_code, title, detail = mapping.get(
        code,
        (
            422,
            "Invalid Backtest Request",
            f"Backtest request failed Alpha validation: {code}.",
        ),
    )
    raise problem(
        request,
        status_code=status_code,
        code=code,
        title=title,
        detail=detail,
        context=context,
    )


def ensure_same_asset_or_raise(
    symbols: list[str], request: Request
) -> tuple[str, list[Any]]:
    classified = []
    for symbol in symbols:
        try:
            classified.append(classify_symbol(symbol))
        except ValueError as exc:
            code = str(exc)
            _raise_backtest_problem(
                request,
                code,
                context={"symbol": symbol.strip().upper()},
            )
    classes = {entry.asset_class for entry in classified}
    if len(classes) > 1:
        _raise_backtest_problem(
            request,
            "mixed_asset_not_supported",
            context={
                "conflicting_symbols": [
                    {"symbol": entry.symbol, "asset_class": entry.asset_class}
                    for entry in classified
                ]
            },
        )
    return classified[0].asset_class, classified


def create_run_from_payload(
    payload: dict[str, Any],
    request: Request,
    *,
    user: User | None = None,
    user_id: str | None = None,
    strategy_id: str | None = None,
    conversation_id: str | None = None,
    persist_in_memory: bool = True,
    language: str | None = None,
) -> BacktestRun:
    symbols = payload.get("symbols") or []
    if not symbols:
        raise problem(
            request,
            status_code=400,
            code="validation_error",
            title="Validation Error",
            detail="Symbol is required.",
        )
    inferred_asset_class, classified_symbols = ensure_same_asset_or_raise(symbols, request)
    requested_asset_class = payload.get("asset_class")
    if requested_asset_class and requested_asset_class != inferred_asset_class:
        _raise_backtest_problem(
            request,
            "asset_class_conflict",
            context={
                "requested_asset_class": requested_asset_class,
                "inferred_asset_class": inferred_asset_class,
                "symbols": [entry.symbol for entry in classified_symbols],
            },
        )
    # Execution Logic
    try:
        config = normalize_backtest_config(payload)
        validate_backtest_config(config)
        metrics = compute_alpha_metrics(config)
    except ValueError as exc:
        _raise_backtest_problem(request, str(exc))
    now = utcnow()
    run = BacktestRun(
        id=store.new_id(),
        conversation_id=conversation_id or payload.get("conversation_id"),
        strategy_id=strategy_id or payload.get("strategy_id"),
        status="completed",
        asset_class=config["asset_class"],
        symbols=config["symbols"],
        allocation_method="equal_weight",
        benchmark_symbol=config["benchmark_symbol"],
        metrics=metrics,
        config_snapshot=config,
        conversation_result_card=build_result_card(
            config, metrics, language=language or (user.language if user else "en")
        ),
        created_at=now,
        chart={
            "equity_curve": [
                config["starting_capital"],
                config["starting_capital"]
                + metrics["aggregate"]["performance"]["profit"],
            ]
        },
        trades=[],
    )
    if persist_in_memory:
        store.backtest_runs[run.id] = run
        if user_id:
            store.backtest_run_owners[run.id] = user_id
    return run




@app.post("/api/v1/backtests/run", response_model=BacktestRunResponse)
def run_backtest(
    payload: BacktestRunRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestRunResponse:
    endpoint = "/api/v1/backtests/run"
    if idempotency_key:
        cached = store.idempotency.get((user.id, endpoint, idempotency_key))
        if cached:
            return BacktestRunResponse(run=cached)

    if supabase_gateway is not None:
        try:
            supabase_gateway.check_and_increment_usage(
                user_id=user.id, resource="backtest_runs", period="day", limit_count=50
            )
            supabase_gateway.check_and_increment_usage(
                user_id=user.id, resource="backtest_runs", period="hour", limit_count=10
            )
        except QuotaExceededError as e:
            raise problem(
                request,
                status_code=429,
                code="too_many_requests",
                title="Quota Exceeded",
                detail=str(e),
                headers={"Retry-After": "60"},
            ) from e

    data = payload.model_dump(exclude_none=True)
    if payload.strategy_id:
        strategy = None
        if supabase_gateway is not None:
            strategy = supabase_gateway.get_strategy(
                user_id=user.id, strategy_id=payload.strategy_id
            )
        else:
            strategy = store.strategies.get(payload.strategy_id)

        if not strategy:
            raise problem(
                request,
                status_code=404,
                code="not_found",
                title="Not Found",
                detail="Strategy not found.",
            )
        strategy_data = strategy.model_dump()
        data = {
            **strategy_data,
            **data,
            "template": strategy.template,
            "asset_class": strategy.asset_class,
            "symbols": data.get("symbols") or strategy.symbols,
            "parameters": strategy.parameters,
            "benchmark_symbol": strategy.benchmark_symbol,
        }
    if not data.get("template"):
        data["template"] = "rsi_mean_reversion"
    run = create_run_from_payload(
        data,
        request,
        user=user,
        user_id=user.id,
        persist_in_memory=supabase_gateway is None,
        language=user.language,
    )
    if supabase_gateway is not None:
        run = supabase_gateway.create_backtest_run(user_id=user.id, run=run)
    if idempotency_key:
        store.idempotency[(user.id, endpoint, idempotency_key)] = run
    return BacktestRunResponse(run=run)


@app.get("/api/v1/backtests/{run_id}", response_model=BacktestRunResponse)
def get_backtest(
    run_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> BacktestRunResponse:
    run = (
        supabase_gateway.get_backtest_run(user_id=user.id, run_id=run_id)
        if supabase_gateway is not None
        else store.backtest_runs.get(run_id)
    )
    if not run:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Backtest run not found.",
        )
    return BacktestRunResponse(run=run)


@app.post("/api/v1/strategies", response_model=StrategyResponse)
def create_strategy(
    payload: StrategyCreate,
    user: User = Depends(current_user),  # noqa: B008
) -> StrategyResponse:
    strategy_name = payload.name
    if not strategy_name:
        suggested = suggest_entity_name(
            entity_type="strategy",
            context=f"Template: {payload.template}\nSymbols: {', '.join(payload.symbols)}",
            language=user.language,
        )
        strategy_name = suggested or f"{', '.join(payload.symbols)} idea"

    if supabase_gateway is not None:
        strategy_payload = payload.model_dump(mode="json")
        strategy_payload["name"] = strategy_name
        strategy_payload["name_source"] = (
            "user_renamed" if payload.name else "ai_generated"
        )
        strategy = supabase_gateway.create_strategy(
            user_id=user.id, payload=strategy_payload
        )
    else:
        now = utcnow()
        benchmark = payload.benchmark_symbol or default_benchmark(payload.asset_class)
        strategy = Strategy(
            id=store.new_id(),
            name=strategy_name,
            name_source="user_renamed" if payload.name else "ai_generated",
            template=payload.template,
            asset_class=payload.asset_class,
            symbols=[classify_symbol(symbol).symbol for symbol in payload.symbols],
            parameters=payload.parameters,
            metrics_preferences=payload.metrics_preferences,
            benchmark_symbol=benchmark,
            created_at=now,
            updated_at=now,
        )
        store.strategies[strategy.id] = strategy
    return StrategyResponse(strategy=strategy)


@app.get("/api/v1/strategies", response_model=PaginatedStrategies)
def list_strategies(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    deleted: bool = Query(False),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedStrategies:
    if supabase_gateway is not None:
        items = supabase_gateway.list_strategies(
            user_id=user.id, limit=None, deleted=deleted
        )
    else:
        items = []
        for item in store.strategies.values():
            if deleted:
                if item.deleted_at is None:
                    continue
            else:
                if item.deleted_at is not None:
                    continue
            items.append(item)

    items.sort(
        key=lambda item: (int(item.pinned), item.updated_at, item.id), reverse=True
    )
    filtered = items
    if cursor:
        cursor_updated_at, cursor_id = _decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_updated_at)
        except ValueError:
            raise _invalid_cursor_problem(request) from None
        # Find the cursor item to get its pinned status, fallback to False if not found for strict tie breaking
        cursor_pinned = next(
            (item.pinned for item in items if item.id == cursor_id), False
        )
        cursor_key = (int(bool(cursor_pinned)), cursor_dt, cursor_id)
        filtered = [
            item
            for item in items
            if (int(item.pinned), item.updated_at, item.id) < cursor_key
        ]
    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = _encode_cursor(last.updated_at.isoformat(), last.id)
    return PaginatedStrategies(items=page_items, next_cursor=next_cursor)


@app.patch("/api/v1/strategies/{strategy_id}", response_model=StrategyResponse)
def patch_strategy(
    strategy_id: str,
    payload: StrategyPatch,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
):
    strategy = None
    if supabase_gateway is not None:
        strategy = supabase_gateway.get_strategy(user_id=user.id, strategy_id=strategy_id)
    else:
        strategy = store.strategies.get(strategy_id)

    if not strategy:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Strategy not found.",
        )

    patch = payload.model_dump(exclude_unset=True)
    if patch.get("name"):
        patch["name_source"] = "user_renamed"

    if supabase_gateway is not None:
        updated = supabase_gateway.patch_strategy(
            user_id=user.id, strategy_id=strategy_id, patch=patch
        )
    else:
        data = strategy.model_dump()
        data.update(patch)
        data["updated_at"] = utcnow()
        updated = Strategy.model_validate(data)
        store.strategies[strategy_id] = updated
    return StrategyResponse(strategy=updated)


@app.delete("/api/v1/strategies/{strategy_id}", response_model=SuccessResponse)
def delete_strategy(
    strategy_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    strategy = None
    if supabase_gateway is not None:
        strategy = supabase_gateway.get_strategy(user_id=user.id, strategy_id=strategy_id)
    else:
        strategy = store.strategies.get(strategy_id)

    if not strategy:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Strategy not found.",
        )

    if supabase_gateway is not None:
        supabase_gateway.soft_delete_strategy(user_id=user.id, strategy_id=strategy_id)
    else:
        store.strategies[strategy_id] = strategy.model_copy(
            update={"deleted_at": utcnow(), "updated_at": utcnow()}
        )
    return SuccessResponse(success=True)


@app.post("/api/v1/collections", response_model=CollectionResponse)
def create_collection(
    payload: CollectionCreate,
    user: User = Depends(current_user),  # noqa: B008
) -> CollectionResponse:
    collection_name = payload.name
    if not collection_name:
        suggested = suggest_entity_name(
            entity_type="collection",
            context="User asked to create a new strategy collection.",
            language=user.language,
        )
        collection_name = suggested or "New collection"

    if supabase_gateway is not None:
        collection = supabase_gateway.create_collection(
            user_id=user.id,
            payload={
                "name": collection_name,
                "name_source": "user_renamed" if payload.name else "ai_generated",
                "created_at": utcnow().isoformat(),
                "updated_at": utcnow().isoformat(),
            },
        )
    else:
        now = utcnow()
        collection = Collection(
            id=store.new_id(),
            name=collection_name,
            name_source="user_renamed" if payload.name else "ai_generated",
            created_at=now,
            updated_at=now,
        )
        store.collections[collection.id] = collection
        store.collection_strategies[collection.id] = set()
    return CollectionResponse(collection=collection)


@app.get("/api/v1/collections", response_model=PaginatedCollections)
def list_collections(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedCollections:
    if supabase_gateway is not None:
        items = supabase_gateway.list_collections(user_id=user.id, limit=None)
    else:
        items = [item for item in store.collections.values() if item.deleted_at is None]
    items.sort(
        key=lambda item: (int(item.pinned), item.updated_at, item.id), reverse=True
    )
    filtered = items
    if cursor:
        cursor_updated_at, cursor_id = _decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_updated_at)
        except ValueError:
            raise _invalid_cursor_problem(request) from None
        # Find the cursor item to get its pinned status, fallback to False if not found for strict tie breaking
        cursor_pinned = next(
            (item.pinned for item in items if item.id == cursor_id), False
        )
        cursor_key = (int(bool(cursor_pinned)), cursor_dt, cursor_id)
        filtered = [
            item
            for item in items
            if (int(item.pinned), item.updated_at, item.id) < cursor_key
        ]
    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = _encode_cursor(last.updated_at.isoformat(), last.id)
    return PaginatedCollections(items=page_items, next_cursor=next_cursor)


@app.patch("/api/v1/collections/{collection_id}", response_model=CollectionResponse)
def patch_collection(
    collection_id: str,
    payload: CollectionPatch,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
):
    collection = None
    if supabase_gateway is not None:
        collection = supabase_gateway.get_collection(
            user_id=user.id, collection_id=collection_id
        )
    else:
        collection = store.collections.get(collection_id)

    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )

    patch = payload.model_dump(exclude_unset=True)
    if patch.get("name"):
        patch["name_source"] = "user_renamed"

    if supabase_gateway is not None:
        updated = supabase_gateway.patch_collection(
            user_id=user.id, collection_id=collection_id, patch=patch
        )
    else:
        data = collection.model_dump()
        data.update(patch)
        data["updated_at"] = utcnow()
        updated = Collection.model_validate(data)
        store.collections[collection_id] = updated
    return CollectionResponse(collection=updated)


@app.delete("/api/v1/collections/{collection_id}", response_model=SuccessResponse)
def delete_collection(
    collection_id: str,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    collection = None
    if supabase_gateway is not None:
        collection = supabase_gateway.get_collection(
            user_id=user.id, collection_id=collection_id
        )
    else:
        collection = store.collections.get(collection_id)

    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )

    if supabase_gateway is not None:
        supabase_gateway.soft_delete_collection(
            user_id=user.id, collection_id=collection_id
        )
    else:
        store.collections[collection_id] = collection.model_copy(
            update={"deleted_at": utcnow(), "updated_at": utcnow()}
        )
    return SuccessResponse(success=True)


@app.post(
    "/api/v1/collections/{collection_id}/strategies", response_model=CollectionResponse
)
def attach_strategies(
    collection_id: str,
    payload: CollectionAttach,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> CollectionResponse:
    if supabase_gateway is not None:
        try:
            updated = supabase_gateway.attach_strategies(
                user_id=user.id,
                collection_id=collection_id,
                strategy_ids=payload.strategy_ids,
            )
            if not updated:
                raise problem(
                    request,
                    status_code=404,
                    code="not_found",
                    title="Not Found",
                    detail="Collection not found.",
                )
            return CollectionResponse(collection=updated)
        except ValueError as exc:
            raise problem(
                request,
                status_code=400,
                code="bad_request",
                title="Bad Request",
                detail=str(exc),
            ) from exc

    collection = store.collections.get(collection_id)
    if not collection:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Collection not found.",
        )
    attached = store.collection_strategies.setdefault(collection_id, set())
    for strategy_id in payload.strategy_ids:
        if strategy_id in store.strategies:
            attached.add(strategy_id)
    updated = collection.model_copy(
        update={"strategy_count": len(attached), "updated_at": utcnow()}
    )
    store.collections[collection_id] = updated
    return CollectionResponse(collection=updated)


@app.delete(
    "/api/v1/collections/{collection_id}/strategies/{strategy_id}",
    response_model=SuccessResponse,
)
def detach_strategy(
    collection_id: str,
    strategy_id: str,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    if supabase_gateway is not None:
        supabase_gateway.detach_strategy(
            user_id=user.id, collection_id=collection_id, strategy_id=strategy_id
        )
    else:
        store.collection_strategies.setdefault(collection_id, set()).discard(strategy_id)
        collection = store.collections.get(collection_id)
        if collection:
            store.collections[collection_id] = collection.model_copy(
                update={
                    "strategy_count": len(store.collection_strategies[collection_id]),
                    "updated_at": utcnow(),
                }
            )
    return SuccessResponse(success=True)


@app.get("/api/v1/history", response_model=PaginatedHistory)
def history(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    deleted: bool = Query(False),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedHistory:
    if supabase_gateway is not None:
        raw = supabase_gateway.list_history_rows(
            user_id=user.id, limit=None, deleted=deleted
        )
        items: list[HistoryItem] = []
        for run in raw["runs"]:
            items.append(
                HistoryItem(
                    type="run",
                    id=run["id"],
                    title=run["conversation_result_card"]["title"],
                    subtitle=run["conversation_result_card"]["rows"][0]["value"],
                    created_at=run["created_at"],
                    conversation_id=run.get("conversation_id"),
                )
            )
        for c in raw["conversations"]:
            items.append(
                HistoryItem(
                    type="chat",
                    id=c["id"],
                    title=c["title"],
                    subtitle=c["last_message_preview"] or "No messages yet",
                    pinned=c["pinned"],
                    created_at=c["updated_at"],
                )
            )
        for s in raw["strategies"]:
            items.append(
                HistoryItem(
                    type="strategy",
                    id=s["id"],
                    title=s["name"],
                    subtitle=", ".join(s["symbols"]),
                    pinned=s["pinned"],
                    created_at=s["updated_at"],
                )
            )
        for col in raw["collections"]:
            items.append(
                HistoryItem(
                    type="collection",
                    id=col["id"],
                    title=col["name"],
                    subtitle=f"{col.get('strategy_count', 0)} strategies",
                    pinned=col["pinned"],
                    created_at=col["updated_at"],
                )
            )
    else:
        items: list[HistoryItem] = []
        for run in store.backtest_runs.values():
            if not deleted:
                items.append(
                    HistoryItem(
                        type="run",
                        id=run.id,
                        title=run.conversation_result_card["title"],
                        subtitle=run.conversation_result_card["rows"][0]["value"],
                        created_at=run.created_at,
                        conversation_id=run.conversation_id,
                    )
                )
        for conversation in store.conversations.values():
            if (
                conversation.deleted_at is not None
                if deleted
                else conversation.deleted_at is None
            ):
                items.append(
                    HistoryItem(
                        type="chat",
                        id=conversation.id,
                        title=conversation.title,
                        subtitle=conversation.last_message_preview or "No messages yet",
                        pinned=conversation.pinned,
                        created_at=conversation.updated_at,
                    )
                )
        for strategy in store.strategies.values():
            if (
                strategy.deleted_at is not None
                if deleted
                else strategy.deleted_at is None
            ):
                items.append(
                    HistoryItem(
                        type="strategy",
                        id=strategy.id,
                        title=strategy.name,
                        subtitle=", ".join(strategy.symbols),
                        pinned=strategy.pinned,
                        created_at=strategy.updated_at,
                    )
                )
        for collection in store.collections.values():
            if (
                collection.deleted_at is not None
                if deleted
                else collection.deleted_at is None
            ):
                items.append(
                    HistoryItem(
                        type="collection",
                        id=collection.id,
                        title=collection.name,
                        subtitle=f"{collection.strategy_count} strategies",
                        pinned=collection.pinned,
                        created_at=collection.updated_at,
                    )
                )

    items.sort(
        key=lambda item: (
            int(item.pinned),
            item.created_at,
            _search_type_rank(item.type),
            item.id,
        ),
        reverse=True,
    )
    filtered = items
    if cursor:
        cursor_created_at, cursor_id = _decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_created_at)
        except ValueError:
            raise _invalid_cursor_problem(request) from None
        cursor_item = next(
            (
                item
                for item in items
                if item.id == cursor_id and item.created_at == cursor_dt
            ),
            None,
        )
        if cursor_item is None:
            raise _invalid_cursor_problem(request)
        cursor_key = (
            int(cursor_item.pinned),
            cursor_dt,
            _search_type_rank(cursor_item.type),
            cursor_id,
        )
        filtered = [
            item
            for item in items
            if (
                int(item.pinned),
                item.created_at,
                _search_type_rank(item.type),
                item.id,
            )
            < cursor_key
        ]
    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last = page_items[-1]
        next_cursor = _encode_cursor(last.created_at.isoformat(), last.id)
    return PaginatedHistory(items=page_items, next_cursor=next_cursor)


@app.get("/api/v1/chat/starter-prompts", response_model=StarterPromptsResponse)
def list_starter_prompts(
    user: User = Depends(current_user),  # noqa: B008
) -> StarterPromptsResponse:
    prompts = get_starter_prompts(user.onboarding.primary_goal)
    return StarterPromptsResponse(prompts=prompts)


@app.get("/api/v1/search", response_model=PaginatedSearch)
def search(
    q: str,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    user: User = Depends(current_user),  # noqa: B008
) -> PaginatedSearch:
    query = q.strip().lower()
    if not query:
        return PaginatedSearch(items=[], next_cursor=None)
    scored_items: list[tuple[int, SearchItem]] = []
    if supabase_gateway is not None:
        raw = supabase_gateway.search_rows(user_id=user.id, query=query, limit=None)
        conversations = raw.get("conversations", [])
        strategies = raw.get("strategies", [])
        collections = raw.get("collections", [])
        runs = raw.get("runs", [])
        for row in conversations:
            item = SearchItem(
                type="chat",
                id=row["id"],
                title=row["title"],
                matched_text=row.get("last_message_preview") or row["title"],
                updated_at=row["updated_at"],
            )
            score = _score_search_item(
                query=query,
                title=row["title"],
                matched_text=item.matched_text,
                pinned=bool(row.get("pinned", False)),
            )
            scored_items.append((score, item))
        for row in strategies:
            symbols = row.get("symbols") or []
            matched_text = ", ".join(symbols) or row["name"]
            symbol_exact_match = any(query == str(symbol).lower() for symbol in symbols)
            item = SearchItem(
                type="strategy",
                id=row["id"],
                title=row["name"],
                matched_text=matched_text,
                updated_at=row["updated_at"],
            )
            score = _score_search_item(
                query=query,
                title=row["name"],
                matched_text=matched_text,
                pinned=bool(row.get("pinned", False)),
                symbol_exact_match=symbol_exact_match,
            )
            scored_items.append((score, item))
        for row in collections:
            item = SearchItem(
                type="collection",
                id=row["id"],
                title=row["name"],
                matched_text=row["name"],
                updated_at=row["updated_at"],
            )
            score = _score_search_item(
                query=query,
                title=row["name"],
                matched_text=row["name"],
                pinned=bool(row.get("pinned", False)),
            )
            scored_items.append((score, item))
        for row in runs:
            card = row.get("conversation_result_card") or {}
            title = card.get("title") or "Backtest run"
            item = SearchItem(
                type="run",
                id=row["id"],
                title=title,
                matched_text=title,
                updated_at=row["created_at"],
                conversation_id=row.get("conversation_id"),
            )
            score = _score_search_item(
                query=query,
                title=title,
                matched_text=title,
                pinned=False,
            )
            scored_items.append((score, item))
    else:
        for conversation in store.conversations.values():
            if conversation.deleted_at:
                continue
            haystack = f"{conversation.title} {conversation.last_message_preview or ''}"
            if query in haystack.lower():
                item = SearchItem(
                    type="chat",
                    id=conversation.id,
                    title=conversation.title,
                    matched_text=conversation.last_message_preview or conversation.title,
                    updated_at=conversation.updated_at,
                )
                score = _score_search_item(
                    query=query,
                    title=conversation.title,
                    matched_text=item.matched_text,
                    pinned=conversation.pinned,
                )
                scored_items.append((score, item))
        for strategy in store.strategies.values():
            if strategy.deleted_at:
                continue
            haystack = f"{strategy.name} {' '.join(strategy.symbols)} {strategy.template}"
            if query in haystack.lower():
                matched_text = ", ".join(strategy.symbols) or strategy.name
                item = SearchItem(
                    type="strategy",
                    id=strategy.id,
                    title=strategy.name,
                    matched_text=matched_text,
                    updated_at=strategy.updated_at,
                )
                score = _score_search_item(
                    query=query,
                    title=strategy.name,
                    matched_text=matched_text,
                    pinned=strategy.pinned,
                    symbol_exact_match=any(
                        query == symbol.lower() for symbol in strategy.symbols
                    ),
                )
                scored_items.append((score, item))
        for collection in store.collections.values():
            if collection.deleted_at:
                continue
            if query in collection.name.lower():
                item = SearchItem(
                    type="collection",
                    id=collection.id,
                    title=collection.name,
                    matched_text=collection.name,
                    updated_at=collection.updated_at,
                )
                score = _score_search_item(
                    query=query,
                    title=collection.name,
                    matched_text=collection.name,
                    pinned=collection.pinned,
                )
                scored_items.append((score, item))
        for run in store.backtest_runs.values():
            title = run.conversation_result_card.get("title", "Backtest run")
            haystack = f"{title} {' '.join(run.symbols)} {run.config_snapshot.get('template', '')}"
            if query in haystack.lower():
                item = SearchItem(
                    type="run",
                    id=run.id,
                    title=title,
                    matched_text=title,
                    updated_at=run.created_at,
                    conversation_id=run.conversation_id,
                )
                score = _score_search_item(
                    query=query,
                    title=title,
                    matched_text=title,
                    pinned=False,
                    symbol_exact_match=any(
                        query == symbol.lower() for symbol in run.symbols
                    ),
                )
                scored_items.append((score, item))

    scored_items.sort(
        key=lambda pair: (
            pair[0],
            pair[1].updated_at,
            _search_type_rank(pair[1].type),
            pair[1].id,
        ),
        reverse=True,
    )
    filtered = scored_items
    if cursor:
        cursor_updated_at, cursor_id = _decode_cursor(cursor, request)
        try:
            cursor_dt = datetime.fromisoformat(cursor_updated_at)
        except ValueError:
            raise _invalid_cursor_problem(request) from None
        cursor_pair = next(
            (
                pair
                for pair in scored_items
                if pair[1].id == cursor_id and pair[1].updated_at == cursor_dt
            ),
            None,
        )
        if cursor_pair is None:
            raise _invalid_cursor_problem(request)
        cursor_score, cursor_item = cursor_pair
        cursor_key = (
            cursor_score,
            cursor_dt,
            _search_type_rank(cursor_item.type),
            cursor_id,
        )
        filtered = [
            pair
            for pair in scored_items
            if (
                pair[0],
                pair[1].updated_at,
                _search_type_rank(pair[1].type),
                pair[1].id,
            )
            < cursor_key
        ]

    page = filtered[: limit + 1]
    has_more = len(page) > limit
    page_items = page[:limit]
    next_cursor = None
    if has_more and page_items:
        last_score, last_item = page_items[-1]
        next_cursor = _encode_cursor(last_item.updated_at.isoformat(), last_item.id)
    return PaginatedSearch(
        items=[item for _, item in page_items],
        next_cursor=next_cursor,
    )


def sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


def _count_completed_runs_for_user(user_id: str) -> int:
    if supabase_gateway is not None:
        try:
            return supabase_gateway.count_completed_runs(user_id=user_id)
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase completed run count failed; using dev memory fallback",
                error=str(exc),
                user_id=user_id,
            )
    return sum(
        1
        for run_id, run in store.backtest_runs.items()
        if store.backtest_run_owners.get(run_id) == user_id and run.status == "completed"
    )


def _persist_onboarding_update(user: User, patch: dict[str, Any]) -> User:
    current = (
        supabase_gateway.get_user(user_id=user.id)
        if supabase_gateway is not None
        else store.users.get(user.id, user)
    )
    if current is None:
        current = user

    onboarding = current.onboarding.model_copy(update=patch)
    updated = current.model_copy(
        update={
            "onboarding": onboarding,
            "updated_at": utcnow(),
        }
    )
    if supabase_gateway is not None:
        try:
            updated = supabase_gateway.update_user(
                user.id, updated.model_dump(mode="json")
            )
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase profile update failed; using dev memory fallback",
                error=str(exc),
                user_id=user.id,
            )
    store.users[user.id] = updated
    return updated


@app.post("/api/v1/chat/stream")
def chat_stream(
    payload: ChatStreamRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: User = Depends(current_user),  # noqa: B008
):
    # Streaming response headers for contract compliance
    headers = {
        "X-Request-Id": request.state.request_id,
        "X-RateLimit-Limit": "200",
        "X-RateLimit-Remaining": "199",
        "X-RateLimit-Reset": "3600",
        "X-Accel-Buffering": "no",  # Recommended in API contract section 12
    }
    if supabase_gateway is not None:
        try:
            supabase_gateway.check_and_increment_usage(
                user_id=user.id,
                resource="chat_messages",
                period="day",
                limit_count=200,
            )
            supabase_gateway.check_and_increment_usage(
                user_id=user.id,
                resource="chat_messages",
                period="minute",
                limit_count=10,
            )
        except QuotaExceededError as e:
            raise problem(
                request,
                status_code=429,
                code="too_many_requests",
                title="Quota Exceeded",
                detail=str(e),
                headers={"Retry-After": "60"},
            ) from e

    current_user_profile = (
        supabase_gateway.get_user(user_id=user.id)
        if supabase_gateway is not None
        else store.users.get(user.id, user)
    )
    if current_user_profile is None:
        current_user_profile = user

    onboarding_goal = parse_onboarding_goal(payload.message)

    conversation = store.conversations.get(payload.conversation_id)
    if conversation is None and supabase_gateway is not None:
        try:
            conversation = supabase_gateway.get_conversation(
                user_id=user.id, conversation_id=payload.conversation_id
            )
        except Exception as exc:
            if not _dev_memory_fallback_enabled():
                raise
            logger.warning(
                "Supabase conversation read failed; using dev memory fallback",
                error=str(exc),
                conversation_id=payload.conversation_id,
            )
    if not conversation:
        raise problem(
            request,
            status_code=404,
            code="not_found",
            title="Not Found",
            detail="Conversation not found.",
        )
    if onboarding_goal is None:
        _create_message(
            user_id=user.id,
            conversation_id=conversation.id,
            role="user",
            content=payload.message,
        )

    onboarding_required = current_user_profile.onboarding.stage in {
        "language_selection",
        "primary_goal_selection",
    }

    def events() -> Iterable[str]:
        if onboarding_required and onboarding_goal is None and not payload.message.strip():
            lang = (
                payload.language
                or conversation.language
                or current_user_profile.language
                or "en"
            )
            from argus.domain.orchestrator import _resolve_language
            is_es = _resolve_language(lang) == "es-419"
            msg = (
                "¿Cuál es tu objetivo principal ahora? No te preocupes, "
                "podrás cambiarlo después en Settings."
                if is_es else
                "What is your current primary goal? Don't worry, "
                "you can change it later in Settings."
            )
            yield sse("status", {"status": "intent_onboarding_prompt"})
            assistant_message = _create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=msg,
            )
            yield sse("token", {"text": msg})
            yield sse("done", {"message_id": assistant_message.id})
            return

        if onboarding_goal is not None:
            _persist_onboarding_update(
                current_user_profile,
                {
                    "stage": "ready",
                    "language_confirmed": True,
                    "primary_goal": onboarding_goal,
                    "completed": False,
                },
            )
            lang = (
                payload.language
                or conversation.language
                or current_user_profile.language
                or "en"
            )
            from argus.domain.orchestrator import _resolve_language
            is_es = _resolve_language(lang) == "es-419"
            if is_es:
                mapping = {
                    "learn_basics": "Perfecto. Te ayudaré con ideas simples para empezar. ¿Qué activo te interesa?",
                    "test_stock_idea": "Perfecto. Cuéntame tu idea de acción y la probamos.",
                    "build_passive_strategy": "Perfecto. Podemos empezar con una idea pasiva tipo DCA.",
                    "explore_crypto": "Perfecto. Empecemos con una idea de cripto que quieras validar.",
                    "surprise_me": "Genial. Te propondré una idea inicial guiada para comenzar.",
                }
            else:
                mapping = {
                    "learn_basics": "Great. I'll keep this beginner-friendly. What asset are you curious about?",
                    "test_stock_idea": "Great. Share the stock idea you want to test and I'll run it.",
                    "build_passive_strategy": "Great. We can start with a passive DCA-style idea.",
                    "explore_crypto": "Great. Let's start with a crypto idea you want to validate.",
                    "surprise_me": "Great. I'll guide you with a starter idea to begin.",
                }
            follow_up = mapping.get(onboarding_goal, mapping["surprise_me"])
            assistant_message = _create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=follow_up,
            )
            yield sse("token", {"text": follow_up})
            yield sse("done", {"message_id": assistant_message.id})
            return

        try:
            runtime_result = run_agent_turn(
                workflow=agent_runtime_workflow,
                session_manager=agent_runtime_session_manager,
                user=UserState(
                    user_id=user.id,
                    display_name=current_user_profile.display_name,
                    language_preference=(
                        payload.language
                        or conversation.language
                        or current_user_profile.language
                        or "en"
                    ),
                ),
                thread_id=conversation.id,
                message=payload.message,
            )
        except Exception as exc:
            logger.exception(
                "Agent runtime chat cutover failed",
                conversation_id=conversation.id,
            )
            yield sse(
                "error",
                {
                    "code": "internal_error",
                    "detail": f"Chat runtime failed: {str(exc)}",
                },
            )
            yield sse("done", {"error": True})
            return

        stage_status = _runtime_stage_status(runtime_result)
        yield sse("status", {"status": stage_status})

        assistant_text = _runtime_result_message(runtime_result)
        confirmation_card = _runtime_confirmation_card(runtime_result)
        if confirmation_card is not None:
            assistant_text = str(confirmation_card["summary"])
        result_card = _runtime_result_card(runtime_result)
        envelope = _runtime_result_envelope(runtime_result)
        run = None

        if result_card is not None:
            run = _persist_runtime_backtest_run(
                user=user,
                conversation=conversation,
                result_card=result_card,
                envelope=envelope,
            )
            _persist_onboarding_update(
                current_user_profile,
                {
                    "stage": "completed",
                    "completed": True,
                    "language_confirmed": True,
                    "primary_goal": current_user_profile.onboarding.primary_goal
                    or "surprise_me",
                },
            )

        metadata: dict[str, Any] = {
            "conversation_mode": (
                "result_review"
                if result_card is not None
                else "confirm"
                if stage_status == "await_approval"
                else "setup"
                if stage_status == "await_user_reply"
                else "guide"
            ),
            "agent_runtime_stage_outcome": stage_status,
        }
        if run is not None:
            metadata["latest_run_id"] = run.id

        assistant_message = None
        if assistant_text is not None:
            assistant_message = _create_message(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_text,
                metadata=metadata,
            )
            if confirmation_card is None:
                yield sse("token", {"text": assistant_text})

        if confirmation_card is not None:
            yield sse("confirmation", {"confirmation": confirmation_card})

        if run is not None:
            yield sse("result", {"run": run.model_dump(mode="json")})

        yield sse(
            "done",
            {"message_id": assistant_message.id if assistant_message is not None else None},
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers=headers,
    )


@app.post("/api/v1/feedback", response_model=SuccessResponse)
def feedback(
    payload: FeedbackRequest,
    request: Request,
    user: User = Depends(current_user),  # noqa: B008
) -> SuccessResponse:
    """
    Submit user feedback, bug reports, or feature requests.
    """
    if supabase_gateway is not None:
        supabase_gateway.create_feedback(
            user_id=user.id,
            feedback_type=payload.type,
            message=payload.message,
            context=payload.context,
        )
    else:
        store.feedback.append(
            {
                "id": store.new_id(),
                "user_id": user.id,
                "type": payload.type,
                "message": payload.message,
                "context": payload.context,
                "created_at": utcnow(),
            }
        )

    logger.info(
        "Feedback received",
        user_id=user.id,
        type=payload.type,
        message_len=len(payload.message),
    )

    return SuccessResponse(success=True)
