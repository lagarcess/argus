"""Usage allowance contract: per-window truth keyed by operation class.

Compute is free and unlimited, grounding is metered per retrieval, execution
per run. The windows underneath (hour, day, guest_session) are shared by every
metered class; an unbounded class carries the same keys with nothing in them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


class UsageWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(ge=0)
    used: int = Field(ge=0)
    remaining: int = Field(ge=0)
    period_end: datetime


class UsageAllowance(BaseModel):
    """Backend-derived allowance truth for the account's active windows."""

    model_config = ConfigDict(frozen=True)

    hour: UsageWindow | None
    day: UsageWindow | None
    guest_session: UsageWindow | None
    available_now: bool
    limiting_window: Literal["hour", "day", "guest_session"]


class UnboundedAllowance(BaseModel):
    """An operation class no account window bounds, so nothing decrements.

    Compute is never metered. A signed-in account's grounding is bounded only
    by the shared research ceiling, a circuit breaker rather than an allowance.
    """

    model_config = ConfigDict(frozen=True)

    hour: None = None
    day: None = None
    guest_session: None = None
    available_now: Literal[True] = True
    limiting_window: None = None


class UsageAllowances(BaseModel):
    """Allowance truth keyed by operation class.

    Compute is free and unlimited, grounding is metered per retrieval, and
    execution is metered per run.
    """

    model_config = ConfigDict(frozen=True)

    compute: UnboundedAllowance
    grounding: UsageAllowance | UnboundedAllowance
    execution: UsageAllowance

    # Deployed web bundles read these until they reload. Both derive from the
    # classes so they cannot drift; they are removed after the first promotion
    # that carries the operation-class keys.
    @computed_field(json_schema_extra={"deprecated": True})  # type: ignore[prop-decorator]
    @property
    def messages(self) -> UnboundedAllowance:
        return self.compute

    @computed_field(json_schema_extra={"deprecated": True})  # type: ignore[prop-decorator]
    @property
    def backtests(self) -> UsageAllowance:
        return self.execution


class UsageAllowanceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowances: UsageAllowances
