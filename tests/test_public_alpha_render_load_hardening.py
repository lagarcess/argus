from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "benchmarks" / "public_alpha_render_load.py"


def _load_module() -> Any:
    module_name = "public_alpha_render_load_hardening_under_test"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class _Response:
    def __init__(
        self,
        status_code: int,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.request = httpx.Request("POST", "https://example.test")

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "request failed",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )


class _ServiceRoleSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, path: str, *, json: dict[str, Any]) -> _Response:
        self.calls.append((path, json))
        if path == "/auth/v1/admin/generate_link":
            return _Response(
                200,
                {
                    "hashed_token": "hashed-secret",
                    "verification_type": "magiclink",
                },
            )
        if path == "/auth/v1/verify":
            return _Response(200, {"access_token": "access-secret"})
        raise AssertionError(f"unexpected path: {path}")


def _completed_case(
    module: Any,
    case_id: str,
    *,
    observed_capacity: dict[str, int] | None = None,
) -> dict[str, Any]:
    admitted = module.CASE_ADMISSIONS[case_id]
    is_retry = case_id.endswith("_retry")
    failure_codes: list[str] = []
    terminal_status = "succeeded"
    if case_id == "invalid_envelope_retry":
        failure_codes = ["invalid_job_contract"]
        terminal_status = "failed"
    elif case_id == "upstream_transient_retry":
        failure_codes = ["failed_upstream"]
    return {
        "case_id": case_id,
        "started_at": "2026-07-30T00:00:00+00:00",
        "finished_at": "2026-07-30T00:00:01+00:00",
        "admitted": admitted,
        "rejected": 0,
        "observed_capacity": observed_capacity
        or {
            "running": 5
            if case_id in {"global_five", "global_five_running_ten_queued"}
            else 1,
            "queued": 10
            if case_id == "global_five_running_ten_queued"
            else 2
            if case_id == "same_user_one_running_two_queued"
            else 0,
        },
        "wall_time_ms": {"p50": 70.0, "p95": 70.0},
        "queue_to_start_ms": {"p50": 20.0, "p95": 20.0},
        "start_to_finish_ms": {"p50": 35.0, "p95": 35.0},
        "terminal_statuses": {terminal_status: admitted},
        "render_task_run_ids": [f"task-{index}" for index in range(admitted)],
        "retry_attempts": [1 if is_retry else 0 for _ in range(admitted)],
        "failure_codes": failure_codes,
    }


def _successful_report(module: Any) -> dict[str, Any]:
    return {
        "schema_version": module.SCHEMA_VERSION,
        "status": "succeeded",
        "completeness": "complete",
        "candidate_sha": "a" * 40,
        "generated_at": "2026-07-30T00:00:00+00:00",
        "api_url": "https://api.example.test",
        "app_url": "https://app.example.test",
        "source": module.CAPACITY_LOAD_SOURCE,
        "workflow": {
            "task": "argus-backtests/run_backtest_job",
            "plan": "standard",
            "max_retries": 1,
        },
        "limits": dict(module.LIMITS),
        "cases": [
            _completed_case(module, case_id) for case_id in module.CASE_MANIFEST
        ],
        "cleanup": {
            "status": "completed",
            "auth": {
                "targets": 15,
                "deleted": 15,
                "already_absent": 0,
                "failed": 0,
            },
            "allowlist": {
                "targets": 15,
                "completed": 15,
                "failed": 0,
            },
        },
    }


def test_service_role_session_uses_generate_link_and_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    service_client = _ServiceRoleSession()
    created_clients: list[dict[str, Any]] = []
    application_client = object()

    def _client_factory(**kwargs: Any) -> object:
        created_clients.append(kwargs)
        return application_client

    monkeypatch.setattr(module.httpx, "Client", _client_factory)

    client = module._create_service_role_session_client(
        SimpleNamespace(api_url="https://argus.example", timeout_seconds=30.0),
        service_client,
        SimpleNamespace(label="user-01", email="load-user@example.test"),
    )

    assert client is application_client
    assert service_client.calls == [
        (
            "/auth/v1/admin/generate_link",
            {"type": "magiclink", "email": "load-user@example.test"},
        ),
        (
            "/auth/v1/verify",
            {"token_hash": "hashed-secret", "type": "magiclink"},
        ),
    ]
    assert created_clients == [
        {
            "base_url": "https://argus.example",
            "headers": {"Authorization": "Bearer access-secret"},
            "timeout": 30.0,
            "follow_redirects": True,
        }
    ]


def test_config_uses_locked_real_workflow_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    identities = tuple(
        module.LoadIdentity(
            label=f"public-alpha-load-{index + 1:02d}",
            email=f"load-{index + 1}@example.test",
        )
        for index in range(15)
    )
    required = {
        "ARGUS_PUBLIC_ALPHA_LOAD_IDENTITIES_JSON": "dedicated-identities",
        "ARGUS_PUBLIC_ALPHA_API_URL": "https://api.example.test",
        "ARGUS_PUBLIC_ALPHA_APP_URL": "https://app.example.test",
        "RENDER_API_KEY": "render-secret",
        "ARGUS_PUBLIC_ALPHA_SUPABASE_URL": "https://supabase.example.test",
        "ARGUS_PUBLIC_ALPHA_SUPABASE_SERVICE_ROLE_KEY": "service-secret",
        "ARGUS_PUBLIC_ALPHA_CANDIDATE_SHA": "d" * 40,
    }
    monkeypatch.setenv(
        "ARGUS_BACKTEST_WORKFLOW_TASK",
        "argus-backtests/workflow_proof",
    )
    monkeypatch.setattr(module, "_required_env", lambda name: required[name])
    monkeypatch.setattr(module, "_parse_identities", lambda _: identities)

    config = module._config_from_env(
        SimpleNamespace(
            output_dir=None,
            timeout_seconds=30.0,
            poll_seconds=0.1,
        )
    )

    assert config.workflow_task == "argus-backtests/run_backtest_job"


def test_all_evidence_states_reject_non_real_workflow_task(
    tmp_path: Path,
) -> None:
    module = _load_module()
    config = _config(module, tmp_path)

    final_report = _successful_report(module)
    final_report["workflow"]["task"] = "argus-backtests/workflow_proof"
    with pytest.raises(ValueError, match="workflow task"):
        module.validate_report(final_report)

    measured_report = module._build_measured_report(
        config=config,
        cases=[
            _completed_case(module, case_id) for case_id in module.CASE_MANIFEST
        ],
        cleanup=module._pending_cleanup(
            config,
            [f"user-{index}" for index in range(15)],
        ),
    )
    measured_report["workflow"]["task"] = "argus-backtests/workflow_proof"
    with pytest.raises(ValueError, match="workflow task"):
        module._write_measured_report(
            report=measured_report,
            output_dir=tmp_path,
        )

    partial_report = module._build_partial_report(
        config,
        completed_cases=[],
        failing_case={
            "case_id": "identity_setup",
            "status": "failed",
            "observed_capacity": {},
            "stop_reason": "harness_case_failed",
        },
        cleanup=module._empty_cleanup(),
    )
    partial_report["workflow"]["task"] = "argus-backtests/workflow_proof"
    with pytest.raises(ValueError, match="workflow task"):
        module._validate_partial_report(partial_report)


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        (
            [{"status": "running", "user_id": f"user-{index}"} for index in range(6)],
            "global_running_exceeded",
        ),
        (
            [{"status": "queued", "user_id": f"user-{index}"} for index in range(11)],
            "global_queued_exceeded",
        ),
        (
            [
                {"status": "running", "user_id": "same-user"},
                {"status": "running", "user_id": "same-user"},
            ],
            "same_user_running_exceeded",
        ),
        (
            [
                {"status": "queued", "user_id": "same-user"},
                {"status": "queued", "user_id": "same-user"},
                {"status": "queued", "user_id": "same-user"},
            ],
            "same_user_queued_exceeded",
        ),
    ],
)
def test_capacity_sample_fails_immediately_above_upper_bounds(
    rows: list[dict[str, str]],
    reason: str,
) -> None:
    module = _load_module()
    sample = module._capacity_sample(rows)

    with pytest.raises(module.CapacityEnvelopeStop, match=reason) as exc_info:
        module._enforce_capacity_bounds("global_five", sample)

    assert exc_info.value.reason == reason
    assert exc_info.value.observed_capacity == sample


@pytest.mark.parametrize(
    ("case_id", "observed_capacity"),
    [
        ("global_five", {"running": 6, "queued": 0}),
        ("global_five_running_ten_queued", {"running": 5, "queued": 11}),
        ("same_user_one_running_two_queued", {"running": 1, "queued": 3}),
    ],
)
def test_report_validation_requires_exact_simultaneous_capacity(
    case_id: str,
    observed_capacity: dict[str, int],
) -> None:
    module = _load_module()
    report = _successful_report(module)
    report["cases"] = [
        _completed_case(
            module,
            item["case_id"],
            observed_capacity=observed_capacity
            if item["case_id"] == case_id
            else None,
        )
        for item in report["cases"]
    ]

    with pytest.raises(ValueError, match="capacity"):
        module.validate_report(report)


def test_cleanup_continues_after_failures_and_retry_is_idempotent() -> None:
    module = _load_module()
    config = SimpleNamespace(
        identities=(
            SimpleNamespace(email="one@example.test"),
            SimpleNamespace(email="two@example.test"),
            SimpleNamespace(email="three@example.test"),
        )
    )

    class _CleanupClient:
        def __init__(self) -> None:
            self.round = 1
            self.calls: list[str] = []

        def delete(self, path: str, **_: Any) -> _Response:
            self.calls.append(path)
            if path.startswith("/auth/v1/admin/users/"):
                user_id = path.rsplit("/", maxsplit=1)[-1]
                if self.round == 1 and user_id == "user-2":
                    return _Response(500)
                if self.round == 2 and user_id in {"user-1", "user-3"}:
                    return _Response(404)
            return _Response(204)

    client = _CleanupClient()
    first = module._cleanup_temporary_identities(
        config=config,
        client=client,
        user_ids=["user-1", "user-2", "user-3"],
    )

    assert first == {
        "status": "incomplete",
        "auth": {
            "targets": 3,
            "deleted": 2,
            "already_absent": 0,
            "failed": 1,
        },
        "allowlist": {"targets": 3, "completed": 3, "failed": 0},
    }
    assert len(client.calls) == 6

    client.round = 2
    client.calls.clear()
    second = module._cleanup_temporary_identities(
        config=config,
        client=client,
        user_ids=["user-1", "user-2", "user-3"],
    )

    assert second == {
        "status": "completed",
        "auth": {
            "targets": 3,
            "deleted": 1,
            "already_absent": 2,
            "failed": 0,
        },
        "allowlist": {"targets": 3, "completed": 3, "failed": 0},
    }
    assert len(client.calls) == 6


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (None, "2026-07-30T00:00:01Z"),
        ("2026-07-30T00:00:00Z", None),
        ("not-a-timestamp", "2026-07-30T00:00:01Z"),
    ],
)
def test_duration_measurements_fail_closed(
    start: str | None,
    end: str | None,
) -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="timestamp"):
        module._duration_ms(start, end)


def test_partial_report_is_sanitized_and_cannot_validate_as_success(
    tmp_path: Path,
) -> None:
    module = _load_module()
    partial = module._build_partial_report(
        SimpleNamespace(
            candidate_sha="b" * 40,
            api_url="https://api.example.test",
            app_url="https://app.example.test",
            workflow_task="argus-backtests/run_backtest_job",
            identities=tuple(range(15)),
        ),
        completed_cases=[_completed_case(module, "idle_one")],
        failing_case={
            "case_id": "global_five",
            "status": "failed",
            "observed_capacity": {"running": 6, "queued": 0},
            "stop_reason": "global_running_exceeded",
        },
        cleanup={
            "status": "pending",
            "auth": {
                "targets": 15,
                "deleted": 0,
                "already_absent": 0,
                "failed": 15,
            },
            "allowlist": {"targets": 15, "completed": 0, "failed": 15},
        },
    )

    output_path = tmp_path / "partial.json"
    module._write_partial_report(partial, output_path)

    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert persisted["status"] == "failed"
    assert persisted["completeness"] == "partial"
    assert persisted["failing_case"] == {
        "case_id": "global_five",
        "status": "failed",
        "observed_capacity": {"running": 6, "queued": 0},
        "stop_reason": "global_running_exceeded",
    }
    with pytest.raises(ValueError, match="succeeded"):
        module.validate_report(persisted)


def _config(module: Any, tmp_path: Path) -> Any:
    return module.HarnessConfig(
        repo_root=ROOT,
        output_dir=tmp_path,
        api_url="https://api.example.test",
        app_url="https://app.example.test",
        render_api_key="render-secret",
        supabase_url="https://supabase.example.test",
        supabase_service_role_key="service-secret",
        candidate_sha="c" * 40,
        workflow_task="argus-backtests/run_backtest_job",
        identities=tuple(
            module.LoadIdentity(
                label=f"public-alpha-load-{index + 1:02d}",
                email=f"load-{index + 1}@example.test",
            )
            for index in range(15)
        ),
        timeout_seconds=30.0,
        poll_seconds=0.001,
        prompt="Test AAPL",
    )


def test_identity_creation_uses_service_role_without_password() -> None:
    module = _load_module()

    class _IdentityClient:
        def __init__(self) -> None:
            self.user_payloads: list[dict[str, Any]] = []
            self.created = 0

        def get(self, path: str, **_: Any) -> _Response:
            assert path == "/rest/v1/private_alpha_allowlist"
            return _Response(200, [])

        def post(
            self,
            path: str,
            *,
            json: dict[str, Any],
            **_: Any,
        ) -> _Response:
            if path == "/auth/v1/admin/users":
                self.user_payloads.append(json)
                self.created += 1
                return _Response(200, {"id": f"user-{self.created}"})
            assert path == "/rest/v1/private_alpha_allowlist"
            return _Response(204)

    client = _IdentityClient()
    user_ids: list[str] = []
    config = SimpleNamespace(
        identities=(
            module.LoadIdentity(
                label="public-alpha-load-01",
                email="load-user@example.test",
            ),
        )
    )

    module._create_temporary_identities(
        config=config,
        client=client,
        user_ids=user_ids,
    )

    assert user_ids == ["user-1"]
    assert client.user_payloads == [
        {
            "email": "load-user@example.test",
            "email_confirm": True,
            "user_metadata": {"source": module.CAPACITY_LOAD_SOURCE},
        }
    ]
    assert "password" not in client.user_payloads[0]


def test_wait_for_capacity_records_one_exact_simultaneous_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    samples = iter(
        [
            [
                *[
                    {"status": "running", "user_id": f"user-{index}"}
                    for index in range(4)
                ],
                {"status": "queued", "user_id": "user-4"},
            ],
            [
                {"status": "running", "user_id": f"user-{index}"}
                for index in range(5)
            ],
        ]
    )
    monkeypatch.setattr(module, "_fetch_jobs", lambda *_: next(samples))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    observed = {"running": 0, "queued": 0}

    module._wait_for_capacity(
        config=SimpleNamespace(timeout_seconds=30.0, poll_seconds=0.001),
        client=object(),
        case_id="global_five",
        job_ids={"job-1"},
        observed=observed,
        running=5,
        queued=0,
    )

    assert observed == {"running": 5, "queued": 0}


def test_wait_for_capacity_lower_ceiling_preserves_best_observed_sample(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    samples = iter(
        [
            [
                *[
                    {"status": "running", "user_id": f"user-{index}"}
                    for index in range(4)
                ],
                {"status": "queued", "user_id": "user-4"},
            ],
            [
                {"status": "succeeded", "user_id": f"user-{index}"}
                for index in range(5)
            ],
        ]
    )
    monkeypatch.setattr(module, "_fetch_jobs", lambda *_: next(samples))
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    with pytest.raises(
        module.CapacityEnvelopeStop,
        match="capacity_peak_not_reached",
    ) as exc_info:
        module._wait_for_capacity(
            config=SimpleNamespace(timeout_seconds=30.0, poll_seconds=0.001),
            client=object(),
            case_id="global_five",
            job_ids={"job-1"},
            observed={"running": 0, "queued": 0},
            running=5,
            queued=0,
        )

    assert exc_info.value.reason == "capacity_peak_not_reached"
    assert exc_info.value.observed_capacity == {
        "running": 4,
        "queued": 1,
        "max_user_running": 1,
        "max_user_queued": 1,
    }


def test_probe_case_polls_task_and_job_to_retry_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    probe_job = {
        "id": "probe-job",
        "status": "queued",
        "attempts": 0,
        "queued_at": "2026-07-30T00:00:00Z",
        "started_at": "2026-07-30T00:00:01Z",
        "finished_at": "2026-07-30T00:00:02Z",
    }
    rows = iter(
        [
            [
                {
                    **probe_job,
                    "status": "running",
                    "attempts": 1,
                    "finished_at": None,
                }
            ],
            [
                {
                    **probe_job,
                    "status": "failed",
                    "attempts": 2,
                    "failure_code": "invalid_job_contract",
                }
            ],
        ]
    )

    class _Dispatcher:
        def __init__(self, **_: Any) -> None:
            pass

        def dispatch(self, **_: Any) -> dict[str, str]:
            return {"id": "task-run-safe"}

    class _TaskClient:
        calls = 0

        def __init__(self, **_: Any) -> None:
            pass

        def get_task_run(self, _: str) -> dict[str, str]:
            self.calls += 1
            return {"status": "running" if self.calls == 1 else "completed"}

    monkeypatch.setattr(module, "_create_probe_job", lambda **_: probe_job)
    monkeypatch.setattr(module, "_fetch_jobs", lambda *_: next(rows))
    monkeypatch.setattr(module, "RenderWorkflowDispatcher", _Dispatcher)
    monkeypatch.setattr(module, "RenderTaskRunClient", _TaskClient)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)

    case = module._run_probe_case(
        config=SimpleNamespace(
            render_api_key="render-secret",
            workflow_task="argus-backtests/run_backtest_job",
            timeout_seconds=30.0,
            poll_seconds=0.001,
        ),
        service_client=object(),
        seed_job={},
        case_id="invalid_envelope_retry",
        mode="invalid_envelope",
    )

    assert case["retry_attempts"] == [1]
    assert case["terminal_statuses"] == {"failed": 1}
    assert case["failure_codes"] == ["invalid_job_contract"]
    assert case["render_task_run_ids"] == ["task-run-safe"]


class _ClosableClient:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def _completed_cleanup() -> dict[str, Any]:
    return {
        "status": "completed",
        "auth": {
            "targets": 15,
            "deleted": 15,
            "already_absent": 0,
            "failed": 0,
        },
        "allowlist": {"targets": 15, "completed": 15, "failed": 0},
    }


def _mock_harness_boundaries(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_ClosableClient, list[_ClosableClient]]:
    service_client = _ClosableClient()
    session_clients: list[_ClosableClient] = []

    def _create_identities(**kwargs: Any) -> None:
        kwargs["user_ids"].extend(f"user-{index}" for index in range(15))

    def _create_session(*_: Any) -> _ClosableClient:
        client = _ClosableClient()
        session_clients.append(client)
        return client

    monkeypatch.setattr(module, "_service_role_client", lambda _: service_client)
    monkeypatch.setattr(module, "_create_temporary_identities", _create_identities)
    monkeypatch.setattr(module, "_create_service_role_session_client", _create_session)
    monkeypatch.setattr(module, "_prepare_run", lambda **_: object())
    monkeypatch.setattr(
        module,
        "_cleanup_temporary_identities",
        lambda **_: _completed_cleanup(),
    )
    return service_client, session_clients


def _mock_successful_cases(
    module: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "_run_public_case",
        lambda **kwargs: (
            _completed_case(module, kwargs["case_id"]),
            {"id": "seed"},
        ),
    )
    monkeypatch.setattr(
        module,
        "_run_probe_case",
        lambda **kwargs: _completed_case(module, kwargs["case_id"]),
    )


def test_run_harness_completes_all_mocked_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    config = _config(module, tmp_path)
    service_client, session_clients = _mock_harness_boundaries(module, monkeypatch)
    _mock_successful_cases(module, monkeypatch)
    pending_path = tmp_path / "public-alpha-render-load.pending.json"
    lifecycle: list[str] = []

    def _cleanup(**_: Any) -> dict[str, Any]:
        assert pending_path.exists()
        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        assert pending["status"] == "measured"
        assert pending["completeness"] == "complete_measurements_pending_cleanup"
        assert pending["cleanup"]["status"] == "pending"
        with pytest.raises(ValueError, match="succeeded"):
            module.validate_report(pending)
        lifecycle.append("cleanup")
        return _completed_cleanup()

    monkeypatch.setattr(module, "_cleanup_temporary_identities", _cleanup)

    report = module.run_harness(config)

    assert lifecycle == ["cleanup"]
    assert report["status"] == "succeeded"
    assert [case["case_id"] for case in report["cases"]] == list(module.CASE_MANIFEST)
    assert (tmp_path / "public-alpha-render-load.json").exists()
    assert not pending_path.exists()
    assert service_client.close_calls == 1
    assert len(session_clients) == 18
    assert all(client.close_calls == 1 for client in session_clients)


def test_final_success_write_failure_preserves_pre_cleanup_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    config = _config(module, tmp_path)
    _mock_harness_boundaries(module, monkeypatch)
    _mock_successful_cases(module, monkeypatch)
    cleanup_calls: list[bool] = []

    def _cleanup(**_: Any) -> dict[str, Any]:
        cleanup_calls.append(True)
        return _completed_cleanup()

    monkeypatch.setattr(module, "_cleanup_temporary_identities", _cleanup)
    monkeypatch.setattr(
        module,
        "write_report",
        lambda **_: (_ for _ in ()).throw(OSError("final promotion failed")),
    )

    with pytest.raises(OSError, match="final promotion failed"):
        module.run_harness(config)

    pending_path = tmp_path / "public-alpha-render-load.pending.json"
    assert cleanup_calls == [True]
    assert pending_path.exists()
    pending = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending["status"] == "measured"
    assert pending["completeness"] == "complete_measurements_pending_cleanup"
    assert pending["cleanup"]["status"] == "pending"
    assert [case["case_id"] for case in pending["cases"]] == list(
        module.CASE_MANIFEST
    )
    with pytest.raises(ValueError, match="succeeded"):
        module.validate_report(pending)


def test_run_harness_persists_partial_before_cleanup_and_returns_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    config = _config(module, tmp_path)
    _mock_harness_boundaries(module, monkeypatch)

    def _public_case(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        if kwargs["case_id"] == "global_five":
            raise module.CapacityEnvelopeStop(
                case_id="global_five",
                reason="global_running_exceeded",
                observed_capacity={
                    "running": 6,
                    "queued": 0,
                    "max_user_running": 1,
                    "max_user_queued": 0,
                },
            )
        return _completed_case(module, kwargs["case_id"]), {"id": "seed"}

    writes: list[str] = []
    original_write = module._write_partial_report

    def _tracking_write(report: Any, output_path: Path) -> None:
        writes.append(str(report["cleanup"]["status"]))
        original_write(report, output_path)

    monkeypatch.setattr(module, "_run_public_case", _public_case)
    monkeypatch.setattr(module, "_write_partial_report", _tracking_write)

    report = module.run_harness(config)

    assert writes == ["pending", "completed"]
    assert report["status"] == "failed"
    assert report["completed_cases"][0]["case_id"] == "idle_one"
    assert report["failing_case"]["stop_reason"] == "global_running_exceeded"
    assert report["cleanup"]["status"] == "completed"
    assert (tmp_path / "public-alpha-render-load.partial.json").exists()
    with pytest.raises(ValueError, match="succeeded"):
        module.validate_report(report)


def test_run_harness_reports_incomplete_cleanup_as_failed_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    config = _config(module, tmp_path)
    _mock_harness_boundaries(module, monkeypatch)
    monkeypatch.setattr(
        module,
        "_run_public_case",
        lambda **kwargs: (
            _completed_case(module, kwargs["case_id"]),
            {"id": "seed"},
        ),
    )
    monkeypatch.setattr(
        module,
        "_run_probe_case",
        lambda **kwargs: _completed_case(module, kwargs["case_id"]),
    )
    monkeypatch.setattr(
        module,
        "_cleanup_temporary_identities",
        lambda **_: {
            "status": "incomplete",
            "auth": {
                "targets": 15,
                "deleted": 14,
                "already_absent": 0,
                "failed": 1,
            },
            "allowlist": {"targets": 15, "completed": 15, "failed": 0},
        },
    )

    report = module.run_harness(config)

    assert report["status"] == "failed"
    assert report["completeness"] == "partial"
    assert len(report["completed_cases"]) == 6
    assert report["failing_case"] == {
        "case_id": "cleanup",
        "status": "failed",
        "observed_capacity": {},
        "stop_reason": "cleanup_incomplete",
    }
    assert report["cleanup"]["auth"]["failed"] == 1


def test_partial_artifact_write_failure_does_not_skip_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    config = _config(module, tmp_path)
    _mock_harness_boundaries(module, monkeypatch)
    cleanup_calls: list[bool] = []

    def _stop_case(**kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        raise module.CapacityEnvelopeStop(
            case_id=kwargs["case_id"],
            reason="capacity_peak_timeout",
            observed_capacity={"running": 4, "queued": 0},
        )

    def _cleanup(**_: Any) -> dict[str, Any]:
        cleanup_calls.append(True)
        return _completed_cleanup()

    monkeypatch.setattr(module, "_run_public_case", _stop_case)
    monkeypatch.setattr(module, "_cleanup_temporary_identities", _cleanup)
    monkeypatch.setattr(
        module,
        "_write_partial_report",
        lambda *_: (_ for _ in ()).throw(OSError("artifact unavailable")),
    )

    with pytest.raises(OSError, match="artifact unavailable"):
        module.run_harness(config)

    assert cleanup_calls == [True]


def test_main_returns_nonzero_for_partial_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    config = _config(module, tmp_path)
    monkeypatch.setattr(module, "_config_from_env", lambda _: config)
    monkeypatch.setattr(
        module,
        "run_harness",
        lambda _: {
            "status": "failed",
            "failing_case": {"stop_reason": "global_running_exceeded"},
        },
    )

    assert module.main([]) == 1
