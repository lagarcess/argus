from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from argus.agent_runtime.capabilities.contract import build_default_capability_contract
from argus.agent_runtime.graph.workflow import build_workflow
from argus.agent_runtime.llm_clarifier import OpenRouterClarificationGenerator
from argus.agent_runtime.llm_interpreter import OpenRouterStructuredInterpreter
from argus.agent_runtime.tools.real_backtest import RealBacktestTool
from argus.domain.store import AlphaStore
from argus.domain.supabase_gateway import SupabaseGateway

load_dotenv()

PERSISTENCE_MODE = os.getenv("ARGUS_PERSISTENCE_MODE", "memory").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
CHECKPOINTER_MODE = os.getenv("ARGUS_CHECKPOINTER_MODE", "").strip().lower()
if not CHECKPOINTER_MODE:
    CHECKPOINTER_MODE = (
        "postgres" if PERSISTENCE_MODE == "supabase" and DATABASE_URL else "memory"
    )
agent_runtime_capability_contract = build_default_capability_contract()
store = AlphaStore()
supabase_gateway = SupabaseGateway.from_env() if PERSISTENCE_MODE == "supabase" else None


def build_agent_runtime_workflow(*, checkpointer: Any):
    return build_workflow(
        contract=agent_runtime_capability_contract,
        tool=RealBacktestTool(),
        structured_interpreter=OpenRouterStructuredInterpreter(
            contract=agent_runtime_capability_contract,
        ),
        clarification_generator=OpenRouterClarificationGenerator(),
        checkpointer=checkpointer,
    )


def build_agent_runtime_checkpoint_serde() -> JsonPlusSerializer:
    # Runtime checkpoints are process-local and may include Pydantic state
    # objects that LangGraph's default msgpack serializer cannot encode.
    return JsonPlusSerializer(
        pickle_fallback=True,
        allowed_msgpack_modules=[
            ("argus.agent_runtime.state.models", "ArtifactReference"),
            ("argus.agent_runtime.state.models", "ConfirmationPayload"),
            ("argus.agent_runtime.state.models", "ConversationMessage"),
            ("argus.agent_runtime.state.models", "FinalResponsePayload"),
            ("argus.agent_runtime.state.models", "ResolutionProvenance"),
            ("argus.agent_runtime.state.models", "ResponseIntent"),
            ("argus.agent_runtime.state.models", "ResponseProfile"),
            ("argus.agent_runtime.state.models", "ResponseProfileOverrides"),
            ("argus.agent_runtime.graph.workflow", "WorkflowStageOutcome"),
            ("argus.agent_runtime.state.models", "RunState"),
            ("argus.agent_runtime.state.models", "StrategySummary"),
            ("argus.agent_runtime.state.models", "StructuredActionContext"),
            ("argus.agent_runtime.state.models", "TaskSnapshot"),
            ("argus.agent_runtime.state.models", "ToolCallRecord"),
            ("argus.agent_runtime.state.models", "UserState"),
            ("argus.agent_runtime.state.models", "UnsupportedConstraint"),
        ],
    )


def build_agent_runtime_checkpointer() -> MemorySaver:
    return MemorySaver(
        serde=build_agent_runtime_checkpoint_serde()
    )


def get_agent_runtime_workflow(request: Request | None = None):
    target_app = request.app if request is not None else None
    if target_app is None:
        checkpointer = build_agent_runtime_checkpointer()
        return build_agent_runtime_workflow(checkpointer=checkpointer)

    workflow = getattr(target_app.state, "agent_runtime_workflow", None)
    if workflow is None:
        checkpointer = build_agent_runtime_checkpointer()
        target_app.state.agent_runtime_checkpointer = checkpointer
        workflow = build_agent_runtime_workflow(checkpointer=checkpointer)
        target_app.state.agent_runtime_workflow = workflow
    return workflow


def reset_agent_runtime_workflow(app: FastAPI) -> None:
    checkpointer = build_agent_runtime_checkpointer()
    app.state.agent_runtime_checkpointer = checkpointer
    app.state.agent_runtime_workflow = build_agent_runtime_workflow(
        checkpointer=checkpointer
    )
