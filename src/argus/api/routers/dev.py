from __future__ import annotations

from fastapi import APIRouter, Request

from argus.api import state as api_state
from argus.api.schemas import SuccessResponse

router = APIRouter(prefix="/api/v1", tags=["dev"])


@router.post("/dev/reset", response_model=SuccessResponse)
def dev_reset(request: Request) -> SuccessResponse:
    api_state.store.reset()
    if api_state.PERSISTENCE_MODE != "supabase":
        api_state.reset_agent_runtime_workflow(request.app)
    api_state.store.get_or_create_dev_user()
    return SuccessResponse(success=True)
