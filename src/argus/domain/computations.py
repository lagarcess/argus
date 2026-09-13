"""Compute kernels a decision can re-run, keyed by computation kind.

The backtest is the first kind, not an exception. Its re-run is the typed
retest projection, which never executes anything: a backtest earns its
confirmation by cost (operating rule 2). Cheap kinds compute in-process when
the decision is opened. Kinds are registered as data, and the dispatcher
never branches on a name.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from argus.api.decision_contract import (
    DecisionComputation,
    DecisionRerun,
    DecisionRerunReasonCode,
)

BACKTEST_COMPUTATION_KIND = "backtest"


@dataclass(frozen=True)
class RerunContext:
    """Owner-scoped readers a kernel may need; the API layer binds them."""

    load_run: Callable[[str], Mapping[str, Any] | None]
    today: date


@dataclass(frozen=True)
class ComputationKernel:
    """A registered kind: typed inputs and the function that re-runs them."""

    kind: str
    inputs_model: type[BaseModel]
    compute: Callable[[BaseModel, RerunContext], DecisionRerun]
    # A backtest's inputs are its immutable run; editing them is a new run.
    inputs_editable: bool = True


class InvalidComputationInputs(ValueError):
    """The merged inputs do not satisfy the kernel's typed input model."""

    def __init__(self, kind: str, errors: list[dict[str, Any]]) -> None:
        super().__init__(f"Inputs for computation kind {kind!r} are invalid.")
        self.kind = kind
        self.errors = errors


_KERNELS: dict[str, ComputationKernel] = {}


def register_kernel(kernel: ComputationKernel, *, replace: bool = False) -> None:
    if kernel.kind in _KERNELS and not replace:
        raise ValueError(f"Computation kind {kernel.kind!r} is already registered.")
    _KERNELS[kernel.kind] = kernel


def unregister_kernel(kind: str) -> None:
    _KERNELS.pop(kind, None)


def kernel_for(kind: str) -> ComputationKernel | None:
    return _KERNELS.get(kind)


def registered_kinds() -> tuple[str, ...]:
    return tuple(sorted(_KERNELS))


def unavailable_rerun(
    computation: DecisionComputation,
    *,
    inputs: Mapping[str, Any] | None = None,
    reason_code: DecisionRerunReasonCode,
) -> DecisionRerun:
    return DecisionRerun(
        kind=computation.kind,
        inputs=dict(inputs if inputs is not None else computation.inputs),
        status="unavailable",
        reason_code=reason_code,
    )


def rerun_computation(
    computation: DecisionComputation,
    *,
    overrides: Mapping[str, Any] | None,
    context: RerunContext,
) -> DecisionRerun:
    """Re-run ``computation`` with ``overrides`` merged over its stored inputs.

    Raises :class:`InvalidComputationInputs` when the merged inputs fail the
    kernel's typed model; the caller decides whether that is a client error
    (overrides were supplied) or a typed unavailable state (stored inputs
    drifted).
    """
    kernel = kernel_for(computation.kind)
    if kernel is None:
        return unavailable_rerun(computation, reason_code="kernel_unavailable")
    merged: dict[str, Any] = {**computation.inputs, **dict(overrides or {})}
    if overrides and not kernel.inputs_editable:
        return unavailable_rerun(
            computation, inputs=merged, reason_code="inputs_not_editable"
        )
    try:
        typed_inputs = kernel.inputs_model.model_validate(merged)
    except ValidationError as exc:
        raise InvalidComputationInputs(computation.kind, exc.errors()) from exc
    return kernel.compute(typed_inputs, context)


class BacktestRerunInputs(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_run_id: str = Field(min_length=1)


def _rerun_backtest(inputs: BaseModel, context: RerunContext) -> DecisionRerun:
    # Imported lazily: run_dossiers reaches into agent_runtime for the
    # retest materializer, and this module must stay importable from schemas.
    from argus.domain.run_dossiers import project_retest_action

    typed = BacktestRerunInputs.model_validate(inputs.model_dump())
    computation = DecisionComputation(
        kind=BACKTEST_COMPUTATION_KIND,
        inputs={"source_run_id": typed.source_run_id},
    )
    run = context.load_run(typed.source_run_id)
    if run is None:
        return unavailable_rerun(computation, reason_code="run_unavailable")
    action = project_retest_action(run=run, today=context.today)
    if action is None:
        return unavailable_rerun(computation, reason_code="retest_unavailable")
    return DecisionRerun(
        kind=computation.kind,
        inputs=dict(computation.inputs),
        status="confirmation_required",
        retest=action,
    )


register_kernel(
    ComputationKernel(
        kind=BACKTEST_COMPUTATION_KIND,
        inputs_model=BacktestRerunInputs,
        compute=_rerun_backtest,
        inputs_editable=False,
    )
)
