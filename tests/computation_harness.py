"""A throwaway compute kernel for proving the decision loop is not backtest-shaped.

The product registers only the backtest kind today. This savings projection is
the second kind the board asks the proof to exercise: a decision recorded
against it, retrieved, and re-run with changed inputs, through the same
registry and endpoints a real calculation will use. It is a test harness and
never ships.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from argus.api.decision_contract import DecisionRerun
from argus.domain.computations import (
    ComputationKernel,
    RerunContext,
    register_kernel,
    unregister_kernel,
)
from pydantic import BaseModel, ConfigDict, Field

SAVINGS_PROJECTION_KIND = "savings_projection"


class SavingsProjectionInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    monthly_amount: float = Field(gt=0)
    months: int = Field(gt=0)
    target_amount: float | None = Field(default=None, gt=0)


def project_savings(inputs: BaseModel, _context: RerunContext) -> DecisionRerun:
    typed = SavingsProjectionInputs.model_validate(inputs.model_dump())
    saved_total = typed.monthly_amount * typed.months
    result: dict[str, Any] = {"saved_total": saved_total}
    if typed.target_amount is not None:
        result["shortfall"] = max(typed.target_amount - saved_total, 0.0)
    return DecisionRerun(
        kind=SAVINGS_PROJECTION_KIND,
        inputs=typed.model_dump(),
        status="computed",
        result=result,
    )


def savings_projection_kernel() -> ComputationKernel:
    return ComputationKernel(
        kind=SAVINGS_PROJECTION_KIND,
        inputs_model=SavingsProjectionInputs,
        compute=project_savings,
    )


@contextmanager
def registered_savings_projection() -> Iterator[ComputationKernel]:
    kernel = savings_projection_kernel()
    register_kernel(kernel)
    try:
        yield kernel
    finally:
        unregister_kernel(SAVINGS_PROJECTION_KIND)
