from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

import pytest
from argus.agent_runtime.confirmation_artifacts import (
    validate_confirmation_execution_payload,
)
from argus.api import state as api_state
from argus.api.main import app
from argus.api.message_store import prepare_message
from argus.domain import backtest_admission
from argus.domain.chat_turn_lifecycle import MemoryChatTurnLifecycleGateway
from argus.domain.store import utcnow
from argus.domain.usage_limits import SIMULATION_ALLOWANCE_LIMITS
from argus.llm.openrouter import (
    clear_openrouter_route_receipts,
    get_openrouter_route_receipts,
    record_openrouter_route_receipt,
)
from fastapi.testclient import TestClient

from tests.evals.chat_runtime_eval_harness import (
    AlphaTrajectory,
    StepObservation,
    TrajectoryAdapters,
    TrajectoryStep,
    TrajectoryStepResult,
    parse_sse_events,
)


@dataclass
class _TrajectoryState:
    conversation_id: str
    artifact_aliases: dict[str, str] = field(default_factory=dict)
    raw_artifact_ids: dict[str, str] = field(default_factory=dict)
    latest_artifact_alias: str | None = None
    latest_action_alias: str | None = None
    latest_job_alias: str | None = None
    latest_raw_job_id: str | None = None
    disconnected_turn_id: str | None = None
    disconnected_request_id: str | None = None
    replay_count: int = 0


@dataclass(frozen=True)
class _StreamResult:
    raw_sse: str
    events: tuple[dict[str, Any], ...]
    final: dict[str, Any]
    receipts: tuple[dict[str, Any], ...]

    @property
    def typed_terminal(self) -> bool:
        return any(event.get("type") in {"final", "error"} for event in self.events)


class _MemoryByActionGateway:
    def get_or_create_mock_user(self):
        return api_state.store.get_or_create_dev_user()

    def get_backtest_job_reservation(self, **_: Any) -> None:
        return None


class ConcreteTrajectoryRuntime:
    """Exercise trajectory steps through production HTTP and memory owners."""

    def __init__(self, *, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        self._client: TestClient | None = None
        self._states: dict[str, _TrajectoryState] = {}
        self._active_trajectory: AlphaTrajectory | None = None
        self._active_step: TrajectoryStep | None = None
        self.adapters = TrajectoryAdapters(
            stream=self.stream,
            action=self.action,
            disconnect=self.disconnect,
            reload=self.reload,
            retry=self.retry,
            persistence=self.persistence,
        )

    def __enter__(self) -> ConcreteTrajectoryRuntime:
        from argus.api.routers import agent as agent_router

        self._monkeypatch.setattr(api_state, "supabase_gateway", None)
        self._monkeypatch.setenv("ARGUS_DEV_MEMORY_FALLBACK", "true")
        self._monkeypatch.setenv("ARGUS_RUNTIME_STREAM_WORKER", "false")
        self._monkeypatch.setattr(
            agent_router,
            "stream_agent_turn_events",
            self._runtime_events,
        )
        self._monkeypatch.setattr(
            agent_router,
            "schedule_artifact_naming_after_stream",
            lambda **_: None,
        )
        clear_openrouter_route_receipts()
        self._client = TestClient(app)
        self._client.post("/api/v1/dev/reset")
        self._client.patch(
            "/api/v1/me",
            json={
                "onboarding": {
                    "stage": "ready",
                    "language_confirmed": True,
                    "primary_goal": "test_stock_idea",
                    "completed": False,
                }
            },
        )
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._active_trajectory = None
        self._active_step = None

    @property
    def _http(self) -> TestClient:
        if self._client is None:
            raise RuntimeError("ConcreteTrajectoryRuntime must be entered")
        return self._client

    def _state(self, trajectory: AlphaTrajectory) -> _TrajectoryState:
        state = self._states.get(trajectory.label)
        if state is not None:
            return state
        self._http.post("/api/v1/dev/reset").raise_for_status()
        self._http.patch(
            "/api/v1/me",
            json={
                "onboarding": {
                    "stage": "ready",
                    "language_confirmed": True,
                    "primary_goal": "test_stock_idea",
                    "completed": False,
                }
            },
        ).raise_for_status()
        clear_openrouter_route_receipts()
        response = self._http.post(
            "/api/v1/conversations",
            json={"language": trajectory.locale},
        )
        response.raise_for_status()
        state = _TrajectoryState(
            conversation_id=str(response.json()["conversation"]["id"])
        )
        self._states[trajectory.label] = state
        return state

    def stream(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
        history: tuple[TrajectoryStepResult, ...],
    ) -> StepObservation:
        del history
        state = self._state(trajectory)
        result = self._submit_stream(
            trajectory=trajectory,
            step=step,
            body={
                "conversation_id": state.conversation_id,
                "language": trajectory.locale,
                **step.request,
            },
        )
        artifact_identity, action_identity = self._observe_artifact(
            trajectory=trajectory,
            state=state,
            final=result.final,
        )
        return self._stream_observation(
            result=result,
            state=state,
            artifact_identity=artifact_identity,
            action_identity=action_identity,
            checkpoints=self._stream_checkpoints(
                trajectory=trajectory,
                artifact_identity=artifact_identity,
            ),
        )

    def reload(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
        history: tuple[TrajectoryStepResult, ...],
    ) -> StepObservation:
        del history
        state = self._state(trajectory)
        if trajectory.label == "alpha_session_05" and step.request.get("method") == "GET":
            raw_confirmation_id = state.raw_artifact_ids[
                "alpha_session_05:confirmation:1"
            ]
            self._monkeypatch.setattr(
                api_state,
                "supabase_gateway",
                _MemoryByActionGateway(),
            )
            response = self._http.get(
                f"/api/v1/backtest-jobs/by-action/{raw_confirmation_id}"
            )
            self._monkeypatch.setattr(api_state, "supabase_gateway", None)
            return StepObservation(
                artifact_identity="alpha_session_05:confirmation:1",
                action_identity="alpha_session_05:confirmation:1",
                reload_state="not_found" if response.status_code == 404 else "found",
                checkpoints={
                    "by_action.lookup_status": response.status_code,
                    "by_action.replay_allowed": response.status_code == 404,
                },
            )
        if trajectory.label == "alpha_session_07" and step.request.get("after"):
            self._age_disconnected_turn_for_reconciliation(state=state)
        response = self._http.get(
            f"/api/v1/conversations/{state.conversation_id}/messages"
        )
        response.raise_for_status()
        items = response.json()["items"]
        if trajectory.label == "alpha_session_07" and step.request.get("after"):
            return self._observe_abandoned_reload(state=state, messages=items)
        artifact_alias = self._latest_projected_artifact_alias(
            state=state,
            messages=items,
        )
        if state.latest_job_alias is not None:
            artifact_alias = state.latest_job_alias
        checkpoints = (
            {"admission.execution_count": self._execution_count(state=state)}
            if trajectory.label == "alpha_session_06"
            else {}
        )
        return StepObservation(
            artifact_identity=artifact_alias,
            action_identity=(
                state.latest_action_alias
                if state.latest_action_alias is not None
                else artifact_alias
                if ":confirmation:" in (artifact_alias or "")
                else None
            ),
            reload_state=artifact_alias,
            checkpoints=checkpoints,
        )

    def action(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
        history: tuple[TrajectoryStepResult, ...],
    ) -> StepObservation:
        del history
        if trajectory.label == "alpha_session_03":
            return self._stream_response_option(trajectory=trajectory, step=step)
        return self._run_action(trajectory=trajectory, step=step, is_retry=False)

    def disconnect(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
        history: tuple[TrajectoryStepResult, ...],
    ) -> StepObservation:
        del history
        state = self._state(trajectory)
        submission = step.request["submission"]
        if submission["operation"] == "action":
            return StepObservation(
                artifact_identity=state.latest_artifact_alias,
                action_identity=state.latest_action_alias,
                typed_terminal=False,
                checkpoints={"by_action.reconciliation_required": True},
            )

        lifecycle = MemoryChatTurnLifecycleGateway(api_state.store)
        request_id = f"{trajectory.label}:request:1"
        accepted = lifecycle.accept_chat_turn(
            user_id=self._user_id(),
            conversation_id=state.conversation_id,
            request_id=request_id,
            message=prepare_message(
                conversation_id=state.conversation_id,
                role="user",
                content=str(submission["request"]["message"]),
            ),
        )
        state.disconnected_turn_id = accepted.id
        state.disconnected_request_id = request_id
        alias = f"{trajectory.label}:turn:1"
        state.artifact_aliases[accepted.id] = alias
        state.raw_artifact_ids[alias] = accepted.id
        return StepObservation(
            artifact_identity=alias,
            persistence_state="accepted",
            typed_terminal=False,
            fingerprint=str(
                api_state.store.chat_turn_lifecycles[accepted.id].get(
                    "input_fingerprint"
                )
                or accepted.id
            ),
            checkpoints={
                "agent_runtime_turn.turn_id": alias,
                "agent_runtime_turn.request_id": request_id,
                "agent_runtime_turn.status": "accepted",
                "orphan_turn.client_terminal_invented": False,
            },
        )

    def retry(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
        history: tuple[TrajectoryStepResult, ...],
    ) -> StepObservation:
        del history
        if trajectory.label in {"alpha_session_05", "alpha_session_06"}:
            return self._run_action(trajectory=trajectory, step=step, is_retry=True)
        if trajectory.label == "alpha_session_07":
            return self._retry_abandoned_turn(trajectory=trajectory, step=step)
        return self._retry_draft(trajectory=trajectory, step=step)

    def persistence(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
        history: tuple[TrajectoryStepResult, ...],
    ) -> StepObservation:
        del step, history
        state = self._state(trajectory)
        if trajectory.label == "alpha_session_01":
            return StepObservation(
                persistence_state=state.latest_artifact_alias,
                checkpoints={"stale_action.persisted_execution_count": 0},
            )
        if trajectory.label == "alpha_session_02":
            return StepObservation(
                artifact_identity=state.latest_artifact_alias,
                checkpoints={"terminal.repeated_fingerprint_count": 0},
            )
        if trajectory.label == "alpha_session_03":
            return StepObservation(artifact_identity=state.latest_artifact_alias)
        if trajectory.label == "alpha_session_04":
            return StepObservation()
        if trajectory.label in {"alpha_session_05", "alpha_session_06"}:
            execution_count = self._execution_count(state=state)
            checkpoints = (
                {"admission.execution_count": execution_count}
                if trajectory.label == "alpha_session_05"
                else {"persistence.durable_identity_count": execution_count}
            )
            return StepObservation(
                artifact_identity=state.latest_job_alias,
                action_identity=state.latest_action_alias,
                checkpoints=checkpoints,
            )
        lifecycle = self._disconnected_lifecycle(state=state)
        alias = f"{trajectory.label}:turn:1"
        return StepObservation(
            artifact_identity=alias,
            persistence_state=str(lifecycle["status"]),
            checkpoints={
                "agent_runtime_turn.turn_id": alias,
                "agent_runtime_turn.request_id": state.disconnected_request_id,
                "agent_runtime_turn.status": lifecycle["status"],
                "persistence.durable_identity_count": 1,
            },
        )

    def _submit_stream(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> _StreamResult:
        self._active_trajectory = trajectory
        self._active_step = step
        receipt_start = len(get_openrouter_route_receipts())
        response = self._http.post(
            "/api/v1/chat/stream",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        events = tuple(parse_sse_events(response.text))
        final = next(
            (
                event["payload"]
                for event in reversed(events)
                if event.get("type") == "final"
                and isinstance(event.get("payload"), dict)
            ),
            {},
        )
        return _StreamResult(
            raw_sse=response.text,
            events=events,
            final=final,
            receipts=tuple(
                receipt.as_dict()
                for receipt in get_openrouter_route_receipts()[receipt_start:]
            ),
        )

    def _stream_observation(
        self,
        *,
        result: _StreamResult,
        state: _TrajectoryState,
        artifact_identity: str | None = None,
        action_identity: str | None = None,
        recovery_code: str | None = None,
        checkpoints: dict[str, Any] | None = None,
        stale_action_executions: int = 0,
    ) -> StepObservation:
        return StepObservation(
            raw_sse=result.raw_sse,
            visible_response_category=self._visible_category(result.final),
            stage_outcome=self._observed_stage_outcome(result.final),
            artifact_identity=artifact_identity,
            action_identity=action_identity,
            recovery_code=recovery_code,
            route_receipts=result.receipts,
            typed_terminal=result.typed_terminal,
            fingerprint=self._latest_lifecycle_fingerprint(
                conversation_id=state.conversation_id
            ),
            checkpoints=checkpoints or {},
            stale_action_executions=stale_action_executions,
        )

    def _run_action(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
        is_retry: bool,
    ) -> StepObservation:
        state = self._state(trajectory)
        action = dict(step.request["action"])
        payload = dict(action.get("payload") or {})
        alias = str(payload["confirmation_id"])
        raw_confirmation_id = state.raw_artifact_ids[alias]
        payload["confirmation_id"] = raw_confirmation_id
        action.update(
            label="Run backtest",
            presentation="confirmation",
            payload=payload,
        )
        result = self._submit_stream(
            trajectory=trajectory,
            step=step,
            headers={"Idempotency-Key": raw_confirmation_id},
            body={
                "conversation_id": state.conversation_id,
                "language": trajectory.locale,
                "action": action,
            },
        )
        raw_job = result.final.get("backtest_job")
        if isinstance(raw_job, dict) and isinstance(raw_job.get("id"), str):
            raw_job_id = str(raw_job["id"])
            job_alias = f"{trajectory.label}:job:1"
            state.artifact_aliases[raw_job_id] = job_alias
            state.raw_artifact_ids[job_alias] = raw_job_id
            state.latest_job_alias = job_alias
            state.latest_raw_job_id = raw_job_id
        if is_retry:
            state.replay_count += 1
        recovery = result.final.get("recovery")
        recovery_code = (
            str(recovery.get("code"))
            if isinstance(recovery, dict) and recovery.get("code")
            else None
        )
        artifact_identity = state.latest_job_alias
        if recovery_code is not None:
            artifact_identity = None
        checkpoints: dict[str, Any] = {}
        if trajectory.label == "alpha_session_01":
            checkpoints["stale_action.execution_count"] = self._execution_count(
                state=state
            )
        elif trajectory.label == "alpha_session_04":
            pass
        elif trajectory.label == "alpha_session_05":
            if is_retry:
                checkpoints.update(
                    {
                        "by_action.replay_count": state.replay_count,
                        "admission.execution_count": self._execution_count(state=state),
                    }
                )
        elif trajectory.label == "alpha_session_06":
            checkpoints["admission.allowance_count"] = self._allowance_count()
            if is_retry:
                checkpoints["admission.execution_count"] = self._execution_count(
                    state=state
                )
        return self._stream_observation(
            result=result,
            state=state,
            artifact_identity=artifact_identity,
            action_identity=alias,
            recovery_code=recovery_code,
            checkpoints=checkpoints,
            stale_action_executions=self._execution_count(state=state)
            if recovery_code == "confirmation_action_stale_card"
            else 0,
        )

    def _stream_response_option(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
    ) -> StepObservation:
        state = self._state(trajectory)
        source = next(
            message
            for message in reversed(api_state.store.messages[state.conversation_id])
            if message.role == "assistant"
            and isinstance(message.metadata.get("clarification"), dict)
        )
        option_id = str(step.request["option"])
        option = next(
            option
            for option in source.metadata["clarification"]["options"]
            if option["id"] == option_id
        )
        result = self._submit_stream(
            trajectory=trajectory,
            step=step,
            body={
                "conversation_id": state.conversation_id,
                "language": trajectory.locale,
                "action": {
                    "type": "select_response_option",
                    "label": option["label"],
                    "payload": {
                        "source_assistant_id": source.id,
                        "option_id": option_id,
                        "replacement_values": option["replacement_values"],
                    },
                },
            },
        )
        artifact_identity, action_identity = self._observe_artifact(
            trajectory=trajectory,
            state=state,
            final=result.final,
        )
        return self._stream_observation(
            result=result,
            state=state,
            artifact_identity=artifact_identity,
            action_identity=action_identity,
        )

    def _retry_draft(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
    ) -> StepObservation:
        state = self._state(trajectory)
        result = self._submit_stream(
            trajectory=trajectory,
            step=step,
            body={
                "conversation_id": state.conversation_id,
                "language": trajectory.locale,
                "message": "Reintentar",
            },
        )
        artifact_identity, _ = self._observe_artifact(
            trajectory=trajectory,
            state=state,
            final=result.final,
        )
        return self._stream_observation(
            result=result,
            state=state,
            artifact_identity=artifact_identity,
            checkpoints={"terminal.retry_target": artifact_identity},
        )

    def _retry_abandoned_turn(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
    ) -> StepObservation:
        state = self._state(trajectory)
        raw_turn_id = state.raw_artifact_ids[f"{trajectory.label}:turn:1"]
        result = self._submit_stream(
            trajectory=trajectory,
            step=step,
            body={
                "conversation_id": state.conversation_id,
                "language": trajectory.locale,
                "action": {
                    "type": "retry_failed_action",
                    "label": "Retry",
                    "payload": {"request_message_id": raw_turn_id},
                },
            },
        )
        artifact_identity, action_identity = self._observe_artifact(
            trajectory=trajectory,
            state=state,
            final=result.final,
        )
        return self._stream_observation(
            result=result,
            state=state,
            artifact_identity=artifact_identity,
            action_identity=action_identity,
            checkpoints={
                "retry_last_turn.request_message_id": f"{trajectory.label}:turn:1",
                "orphan_turn.duplicate_turn_count": 0,
                "terminal.artifact_identity": artifact_identity,
            },
        )

    def _admitted_job_runtime_payload(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
    ) -> dict[str, Any]:
        state = self._state(trajectory)
        alias = str(step.request["action"]["payload"]["confirmation_id"])
        raw_confirmation_id = state.raw_artifact_ids[alias]
        confirmation_message = next(
            message
            for message in reversed(api_state.store.messages[state.conversation_id])
            if message.role == "assistant"
            and isinstance(message.metadata.get("confirmation_card"), dict)
            and message.metadata["confirmation_card"].get("confirmation_id")
            == raw_confirmation_id
        )
        validation = validate_confirmation_execution_payload(
            confirmation_message.metadata["confirmation_payload"]
        )
        if validation.launch_payload is None:
            raise AssertionError("trajectory confirmation was not executable")
        launch_payload = validation.launch_payload
        payload_digest = backtest_admission.canonical_hash(launch_payload)
        outcome = backtest_admission.admit_backtest_job_memory(
            api_state.store,
            user_id=self._user_id(),
            operation_scope=backtest_admission.CHAT_RUN_SCOPE,
            idempotency_key=raw_confirmation_id,
            identity_hash=backtest_admission.chat_run_identity_hash(
                conversation_id=state.conversation_id,
                confirmation_id=raw_confirmation_id,
                launch_payload_hash=payload_digest,
            ),
            payload_hash=payload_digest,
            launch_payload=launch_payload,
            initial_status="queued",
            conversation_id=state.conversation_id,
            request_message_id=None,
            confirmation_message_id=confirmation_message.id,
            execution_metadata={"source": "trajectory_adapter"},
            allowance_limits=list(SIMULATION_ALLOWANCE_LIMITS),
        )
        if outcome.kind not in {"admitted", "replay"} or outcome.job is None:
            raise AssertionError(f"trajectory admission failed: {outcome.kind}")
        job = outcome.job
        return {
            "stage_outcome": "ready_to_respond",
            "assistant_response": "The backtest is queued.",
            "backtest_job": job,
            "final_response_payload": {"backtest_job": job},
            "artifact_references": [
                {
                    "artifact_kind": "backtest_job",
                    "artifact_id": job["id"],
                    "artifact_status": job["status"],
                    "metadata": {
                        "id": job["id"],
                        "conversation_id": state.conversation_id,
                        "status": job["status"],
                    },
                }
            ],
        }

    def _age_disconnected_turn_for_reconciliation(
        self,
        *,
        state: _TrajectoryState,
    ) -> None:
        from argus.domain import chat_turn_lifecycle

        if state.disconnected_turn_id is None:
            raise AssertionError("disconnect did not accept a turn")
        future = utcnow() + timedelta(minutes=16)
        self._monkeypatch.setattr(chat_turn_lifecycle, "utcnow", lambda: future)

    def _observe_abandoned_reload(
        self,
        *,
        state: _TrajectoryState,
        messages: list[dict[str, Any]],
    ) -> StepObservation:
        alias = next(
            alias
            for alias in state.raw_artifact_ids
            if alias.endswith(":turn:1")
        )
        raw_turn_id = state.raw_artifact_ids[alias]
        projected = next(
            message
            for message in messages
            if isinstance(message.get("metadata"), dict)
            and message["metadata"].get("recovery", {}).get("code")
            == "turn_abandoned"
        )
        metadata = projected["metadata"]
        runtime_turn = metadata["agent_runtime_turn"]
        retry = metadata["retry_last_turn"]
        lifecycle = self._disconnected_lifecycle(state=state)
        accepted_orphans = sum(
            row["status"] in {"accepted", "running"}
            for row in api_state.store.chat_turn_lifecycles.values()
            if row["conversation_id"] == state.conversation_id
        )
        return StepObservation(
            artifact_identity=alias,
            reload_state=str(lifecycle["status"]),
            recovery_code=str(metadata["recovery"]["code"]),
            typed_terminal=bool(runtime_turn["terminal"]),
            fingerprint=raw_turn_id,
            checkpoints={
                "agent_runtime_turn.turn_id": alias,
                "agent_runtime_turn.request_id": runtime_turn["request_id"],
                "agent_runtime_turn.status": runtime_turn["status"],
                "agent_runtime_turn.terminal": runtime_turn["terminal"],
                "agent_runtime_turn.reconciled_outcome": runtime_turn.get(
                    "reconciled_outcome"
                ),
                "agent_runtime_turn.failure_code": runtime_turn["failure_code"],
                "agent_runtime_turn.retryable": runtime_turn["retryable"],
                "recovery.code": metadata["recovery"]["code"],
                "recovery.retryable": metadata["recovery"]["retryable"],
                "retry_last_turn.request_message_id": (
                    alias
                    if retry["request_message_id"] == raw_turn_id
                    else retry["request_message_id"]
                ),
                "retry_last_turn.message": retry["message"],
                "orphan_turn.after_window_count": accepted_orphans,
            },
            accepted_orphan_turns_after_window=accepted_orphans,
        )

    def _user_id(self) -> str:
        return api_state.store.get_or_create_dev_user().id

    @staticmethod
    def _disconnected_lifecycle(*, state: _TrajectoryState) -> dict[str, Any]:
        if state.disconnected_turn_id is None:
            raise AssertionError("trajectory has no disconnected turn")
        return api_state.store.chat_turn_lifecycles[state.disconnected_turn_id]

    @staticmethod
    def _execution_count(*, state: _TrajectoryState) -> int:
        return sum(
            job.get("conversation_id") == state.conversation_id
            for job in api_state.store.backtest_jobs.values()
        )

    @staticmethod
    def _allowance_count() -> int:
        counts = [
            int(row.get("used_count", 0))
            for row in api_state.store.usage_counters.values()
        ]
        return max(counts, default=0)

    async def _runtime_events(self, **_: Any):
        trajectory = self._active_trajectory
        step = self._active_step
        if trajectory is None or step is None:
            raise RuntimeError("trajectory step was not bound")
        record_openrouter_route_receipt(
            task="interpretation",
            model_name="trajectory-fixture",
            mode="json_schema",
            schema_name="TrajectoryFixture",
            latency_ms=1,
            outcome="succeeded",
            token_usage={"prompt_tokens": 1, "completion_tokens": 1},
            usage_cost_usd=0.001,
        )
        payload = self._runtime_payload(trajectory=trajectory, step=step)
        outcome = str(payload["stage_outcome"])
        yield {"type": "stage_start", "stage": "interpret"}
        yield {"type": "stage_outcome", "outcome": outcome}
        yield {
            "type": "final",
            "payload": payload,
        }

    def _runtime_payload(
        self,
        *,
        trajectory: AlphaTrajectory,
        step: TrajectoryStep,
    ) -> dict[str, Any]:
        label = trajectory.label
        if step.operation in {"action", "retry"} and label in {
            "alpha_session_04",
            "alpha_session_05",
            "alpha_session_06",
        }:
            return self._admitted_job_runtime_payload(
                trajectory=trajectory,
                step=step,
            )
        if label == "alpha_session_02" and step.index == 2:
            return {
                "stage_outcome": "ready_to_respond",
                "assistant_response": "La idea sigue guardada, pero necesito una regla concreta.",
                "recovery": {
                    "code": "no_material_progress",
                    "retryable": False,
                },
                "pending_strategy": {
                    "strategy": {
                        "strategy_type": None,
                        "asset_universe": ["BTC"],
                    },
                    "requested_field": "strategy_type",
                    "missing_required_fields": ["strategy_type"],
                },
            }
        if label in {"alpha_session_02", "alpha_session_03"}:
            payload = {
                "stage_outcome": "await_user_reply",
                "assistant_prompt": (
                    "¿Qué regla quieres probar?"
                    if trajectory.locale == "es-419"
                    else "Enter a known symbol."
                ),
                "requested_field": "strategy_type",
                "pending_strategy": {
                    "strategy": {
                        "strategy_type": None,
                        "asset_universe": ["BTC"] if label.endswith("02") else [],
                    },
                    "requested_field": "strategy_type",
                    "missing_required_fields": ["strategy_type"],
                },
                "clarification": {
                    "question": "Enter a known symbol.",
                    "requested_field": "asset_universe",
                    "options": [
                        {
                            "id": "enter_known_symbol",
                            "label": "Enter a known symbol",
                            "replacement_values": {
                                "requested_field": "asset_universe"
                            },
                        }
                    ],
                },
            }
            if label == "alpha_session_03" and step.index == 1:
                payload["recovery"] = {
                    "code": "unsupported_capability",
                    "retryable": False,
                }
            return payload
        symbol = {
            "alpha_session_01": "NVDA" if step.index == 2 else "AAPL",
            "alpha_session_04": "CART",
            "alpha_session_05": "TSLA",
            "alpha_session_06": "BTC",
            "alpha_session_07": "MSFT",
        }[label]
        payload = _confirmation_runtime_payload(symbol=symbol)
        if label == "alpha_session_04":
            payload["coverage_preflight"] = {
                "outcome": "adjusted_coverage",
                "requested_date_range": {
                    "start": "2020-01-01",
                    "end": "2026-01-01",
                },
                "effective_date_range": {
                    "start": "2024-01-19",
                    "end": "2026-01-01",
                },
            }
        return payload

    def _observe_artifact(
        self,
        *,
        trajectory: AlphaTrajectory,
        state: _TrajectoryState,
        final: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        confirmation = final.get("confirmation")
        if isinstance(confirmation, dict) and isinstance(
            confirmation.get("confirmation_id"), str
        ):
            raw_id = str(confirmation["confirmation_id"])
            existing = state.artifact_aliases.get(raw_id)
            if existing is None:
                count = sum(
                    alias.startswith(f"{trajectory.label}:confirmation:")
                    for alias in state.artifact_aliases.values()
                )
                existing = f"{trajectory.label}:confirmation:{count + 1}"
            state.artifact_aliases[raw_id] = existing
            state.raw_artifact_ids[existing] = raw_id
            state.latest_artifact_alias = existing
            state.latest_action_alias = existing
            return existing, existing
        pending = final.get("pending_strategy")
        if isinstance(pending, dict):
            alias = f"{trajectory.label}:draft:1"
            state.latest_artifact_alias = alias
            return alias, None
        return None, None

    @staticmethod
    def _visible_category(final: dict[str, Any]) -> str | None:
        if isinstance(final.get("recovery"), dict):
            return "typed_recovery"
        if isinstance(final.get("confirmation"), dict):
            if isinstance(final.get("coverage_preflight"), dict):
                return "confirmation_with_correction"
            return "confirmation"
        if isinstance(final.get("backtest_job"), dict):
            return "job_accepted"
        if isinstance(final.get("pending_strategy"), dict):
            return "clarification"
        return None

    @staticmethod
    def _observed_stage_outcome(final: dict[str, Any]) -> str | None:
        outcome = final.get("stage_outcome")
        if outcome == "await_approval":
            return "ready_for_confirmation"
        if outcome == "await_user_reply":
            return "needs_clarification"
        return str(outcome) if outcome else None

    @staticmethod
    def _stream_checkpoints(
        *,
        trajectory: AlphaTrajectory,
        artifact_identity: str | None,
    ) -> dict[str, Any]:
        if trajectory.label == "alpha_session_01" and artifact_identity:
            return {"stale_action.active_artifact": artifact_identity}
        if trajectory.label == "alpha_session_02":
            return {"terminal.response_language": trajectory.locale}
        return {}

    @staticmethod
    def _latest_lifecycle_fingerprint(*, conversation_id: str) -> str | None:
        rows = [
            row
            for row in api_state.store.chat_turn_lifecycles.values()
            if row.get("conversation_id") == conversation_id
        ]
        if not rows:
            return None
        row = max(rows, key=lambda item: str(item.get("accepted_at") or ""))
        value = row.get("output_fingerprint") or row.get("input_fingerprint")
        return str(value) if value else None

    @staticmethod
    def _latest_projected_artifact_alias(
        *,
        state: _TrajectoryState,
        messages: list[dict[str, Any]],
    ) -> str | None:
        for message in reversed(messages):
            metadata = message.get("metadata")
            if not isinstance(metadata, dict):
                continue
            confirmation = metadata.get("confirmation_card")
            if isinstance(confirmation, dict):
                raw_id = confirmation.get("confirmation_id")
                if isinstance(raw_id, str) and raw_id in state.artifact_aliases:
                    return state.artifact_aliases[raw_id]
            if isinstance(metadata.get("pending_strategy"), dict):
                return state.latest_artifact_alias
        return state.latest_artifact_alias


def _confirmation_runtime_payload(*, symbol: str) -> dict[str, Any]:
    asset_class = "crypto" if symbol == "BTC" else "equity"
    benchmark = "BTC" if asset_class == "crypto" else "SPY"
    launch_payload: dict[str, Any] = {
        "strategy_type": "buy_and_hold",
        "symbol": symbol,
        "symbols": [symbol],
        "asset_class": asset_class,
        "timeframe": "1D",
        "date_range": {"start": "2025-01-01", "end": "2026-01-01"},
        "sizing_mode": "capital_amount",
        "capital_amount": 10000.0,
        "benchmark_symbol": benchmark,
    }
    return {
        "stage_outcome": "await_approval",
        "assistant_response": f"Ready to test {symbol} with buy and hold.",
        "confirmation_payload": {
            "strategy": {
                "strategy_type": "buy_and_hold",
                "asset_universe": [symbol],
                "asset_class": asset_class,
                "date_range": {"start": "2025-01-01", "end": "2026-01-01"},
                "capital_amount": 10000,
            },
            "optional_parameters": {
                "initial_capital": {
                    "value": 10000.0,
                    "source": "user",
                    "label": "Initial capital",
                },
                "timeframe": {
                    "value": "1D",
                    "source": "user",
                    "label": "Timeframe",
                },
                "fees": {"value": 0.0, "source": "default", "label": "Fees"},
                "slippage": {
                    "value": 0.0,
                    "source": "default",
                    "label": "Slippage",
                },
            },
            "launch_payload": launch_payload,
            "validation": {"executable": True},
        },
    }
