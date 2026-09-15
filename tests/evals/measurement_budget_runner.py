"""Serial measurement with durable partial evidence, never a partial scorecard."""

from __future__ import annotations

import asyncio
import json
import traceback
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

import httpx

from tests.evals.measurement_budget import MeasurementCaseFailure


def run_budgeted_cases(
    cases: list[Any],
    *,
    run_case: Callable[[Any], dict[str, Any]],
    budget: Any,
    provenance: Any,
    progress_path: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    current: str | None = None

    def persist(status: str, failure: str | None = None) -> None:
        document = {
            "status": status,
            "provenance": asdict(provenance),
            "planned_case_ids": [case.id for case in cases],
            "interrupted_case_id": current if status == "incomplete" else None,
            "failure_type": failure,
            "budget": budget.snapshot(),
            "results": results,
        }
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = progress_path.with_suffix(".writing")
        temporary.write_text(json.dumps(document, indent=2) + "\n")
        temporary.replace(progress_path)

    persist("running")
    try:
        for case in cases:
            current = case.id
            try:
                with budget.case(case.id):
                    result = run_case(case)
            except (
                MeasurementCaseFailure,
                TimeoutError,
                asyncio.TimeoutError,
                asyncio.CancelledError,
                httpx.TransportError,
            ) as exc:
                infrastructure = isinstance(exc, httpx.TransportError)
                code = "transport_failure" if infrastructure else "runtime_timeout"
                if isinstance(exc, MeasurementCaseFailure):
                    code = "measurement_policy:" + str(exc)
                result = {
                    "id": case.id,
                    "category": case.category,
                    "status": "infrastructure_error" if infrastructure else "failed",
                    "failed_checks": [] if infrastructure else [code],
                    "infrastructure_errors": [
                        {"component": "provider_transport", "code": type(exc).__name__}
                    ]
                    if infrastructure
                    else [],
                    "typed_outcome": {},
                    "prose_judge": None,
                    "route_receipts": [],
                    "expected_fail": None,
                    "failure_trace": [
                        {
                            "file": Path(frame.filename).name,
                            "line": frame.lineno,
                            "function": frame.name,
                        }
                        for frame in traceback.extract_tb(exc.__traceback__)
                    ],
                }
            results.append(result)
            persist("running")
            print(
                f"measurement {len(results)}/{len(cases)} {case.id}: "
                f"{result.get('status', 'unknown')}",
                flush=True,
            )
        budget.assert_complete()
    except BaseException as exc:
        # Includes the uncatchable-by-runtime budget stop and operator interrupt.
        # No exception message, provider body, or credentials enter this report.
        persist("incomplete", type(exc).__name__)
        raise
    persist("completed")
    return results
