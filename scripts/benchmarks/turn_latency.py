"""Client-side measurement for #462; never imported by the product runtime.

Only the timing trace is publishable. ``final`` is kept in memory to follow
canonical actions/jobs; it contains private identifiers and must not be exported.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from argus.domain.backtest_job_scopes import RESEARCH_OPERATION_SCOPE

from scripts.benchmarks.render_internet_benchmark import _confirmation_cards


@dataclass
class StreamObservation:
    timings: dict[str, float] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    final: dict[str, Any] = field(default_factory=dict)
    visible_kind: str | None = None
    error_kind: str | None = None
    error_code: str | None = None
    _buffer: str = ""

    def feed(self, chunk: str, elapsed_ms: float) -> None:
        self._buffer += chunk
        # Normalize only complete CRLF pairs, including pairs split across chunks.
        self._buffer = self._buffer.replace("\r\n", "\n")
        while "\n\n" in self._buffer:
            raw, self._buffer = self._buffer.split("\n\n", 1)
            data = "\n".join(
                line[5:].lstrip() for line in raw.splitlines() if line.startswith("data:")
            )
            if not data:
                continue
            if data == "[DONE]":
                self.timings.setdefault("done_ms", elapsed_ms)
                self.events.append({"type": "done", "at_ms": elapsed_ms})
                continue
            event = json.loads(data)
            kind = event["type"]
            safe: dict[str, Any] = {"type": kind, "at_ms": elapsed_ms}
            if kind == "stage_start":
                self.timings.setdefault("first_stage_ms", elapsed_ms)
                safe["stage"] = event.get("stage")
            elif kind == "stage_outcome":
                safe["outcome"] = event.get("outcome")
            elif kind == "token":
                content = event.get("content", "")
                safe["characters"] = len(content)
                if content.strip():
                    self.timings.setdefault("first_token_ms", elapsed_ms)
                    self._visible("token", elapsed_ms)
            elif kind == "final":
                self.final = event.get("payload") or {}
                self.timings.setdefault("final_ms", elapsed_ms)
                if _confirmation_cards([event]):
                    self._visible("confirmation_card", elapsed_ms)
                else:
                    for value in (
                        self.final,
                        self.final.get("final_response_payload") or {},
                    ):
                        for key in ("result_card", "run", "assistant_response"):
                            if value.get(key):
                                self._visible(key, elapsed_ms)
                                break
            elif kind == "error":
                self.error_kind = "sse_error"
                self.error_code = event.get("code")
                safe["code"] = self.error_code
            self.events.append(safe)

    def _visible(self, kind: str, elapsed_ms: float) -> None:
        if "first_visible_ms" not in self.timings:
            self.timings["first_visible_ms"] = elapsed_ms
            self.visible_kind = kind


def distribution(values: list[float | None]) -> dict[str, Any]:
    """Nearest-rank empirical quantiles; never impute a missing observation."""
    observed = sorted(value for value in values if value is not None)
    if any(not math.isfinite(value) or value < 0 for value in observed):
        raise ValueError("latency must be finite and nonnegative")
    result: dict[str, Any] = {"n": len(observed), "missing": len(values) - len(observed)}
    if observed:
        result.update(
            {
                "min": observed[0],
                "p50": observed[math.ceil(len(observed) * 0.50) - 1],
                "p95": observed[math.ceil(len(observed) * 0.95) - 1],
                "max": observed[-1],
            }
        )
    return result


def stream_turn(client: httpx.Client, body: dict[str, Any], *, headers=None):
    observation = StreamObservation()
    started = time.perf_counter()
    request_id = None
    try:
        with client.stream(
            "POST", "/api/v1/chat/stream", json=body, headers=headers
        ) as response:
            observation.timings["headers_ms"] = (time.perf_counter() - started) * 1000
            request_id = response.headers.get("x-request-id")
            response.raise_for_status()
            for chunk in response.iter_text():
                elapsed_ms = (time.perf_counter() - started) * 1000
                observation.feed(chunk, round(elapsed_ms, 3))
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        observation.error_kind = type(exc).__name__
    observation.timings["stream_close_ms"] = round(
        (time.perf_counter() - started) * 1000, 3
    )
    return observation, request_id, started


def typed_outcome(payload: dict[str, Any]) -> dict[str, Any]:
    """Closed projection: never publish prose, links, user ids or action payloads."""
    research = payload.get("research") or {}
    usage = research.get("usage") or {}
    degraded = research.get("degraded") or {}
    return {
        "stage_outcome": payload.get("stage_outcome"),
        "conversation_mode": payload.get("conversation_mode"),
        "confirmation": bool(
            _confirmation_cards([{"type": "final", "payload": payload}])
        ),
        "run": isinstance(payload.get("run"), dict),
        "research_shape": research.get("shape"),
        "research_degraded": degraded.get("code"),
        "research_cache": usage.get("cache_status"),
        "research_provider_ms": usage.get("latency_ms"),
        "research_cost_usd": usage.get("cost_usd"),
        "research_invocations": usage.get("invocations"),
        "research_source_count": len(research.get("sources") or []),
        "failure_code": payload.get("failure_code"),
    }


def poll_job(
    client: httpx.Client, job_id: str, started: float, *, timeout=660, interval=1
):
    """Completion is receipt of a terminal artifact, not the stream acknowledgement.

    Times are observed upper bounds at the polling client. Server finished_at
    timestamps and the poll interval are recorded separately, not subtracted.
    """
    checks = []
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            response = client.get(f"/api/v1/backtest-jobs/{job_id}")
            response.raise_for_status()
            payload = response.json()
            job = payload["job"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            return {
                "status": "measurement_error",
                "error_kind": type(exc).__name__,
                "polls": checks,
                "completion_ms": None,
            }
        elapsed = round((time.perf_counter() - started) * 1000, 3)
        checks.append({"at_ms": elapsed, "status": job["status"]})
        if job["status"] == "succeeded":
            artifact = (
                "result_message"
                if job.get("operation_scope") == RESEARCH_OPERATION_SCOPE
                else "run"
            )
            if not payload.get(artifact):
                time.sleep(interval)
                continue
        if job["status"] in {"succeeded", "failed", "canceled", "expired"}:
            message = payload.get("result_message") or {}
            metadata = message.get("metadata") or {}
            answer_present = bool(message.get("content") or payload.get("result_readout"))
            evidence = {
                "status": job["status"],
                "operation_scope": job.get("operation_scope"),
                "failure_code": job.get("failure_code"),
                "polls": checks,
                "completion_ms": elapsed,
                "poll_interval_ms": interval * 1000,
                "answer_observed_ms": elapsed if answer_present else None,
                "run_present": bool(payload.get("run")),
                "result_message_present": bool(message),
                "result_readout_source": payload.get("result_readout_source"),
                "result_readout_fallback_used": payload.get(
                    "result_readout_fallback_used"
                ),
                "queued_at": job.get("queued_at"),
                "started_at": job.get("started_at"),
                "finished_at": job.get("finished_at"),
                "result": typed_outcome(metadata),
            }
            return evidence
        time.sleep(interval)
    return {"status": "measurement_timeout", "polls": checks, "completion_ms": None}
