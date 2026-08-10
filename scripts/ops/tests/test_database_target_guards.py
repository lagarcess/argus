from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Callable

import pytest

OPS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = OPS_DIR.parents[1]

CONNECTION_ENV = (
    "DATABASE_URL",
    "ARGUS_WORKFLOW_DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
    "ARGUS_STALE_JOBS_SUPABASE_URL",
    "ARGUS_CANARY_SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "ARGUS_STALE_JOBS_SUPABASE_SERVICE_ROLE_KEY",
    "ARGUS_CANARY_SUPABASE_SERVICE_ROLE_KEY",
)


class UnexpectedDatabaseAccess(AssertionError):
    """Raised if an entry point reaches its gateway without an explicit target."""


def _package(name: str) -> ModuleType:
    package = ModuleType(name)
    package.__path__ = []  # type: ignore[attr-defined]
    return package


def _unexpected_gateway() -> object:
    raise UnexpectedDatabaseAccess("database gateway was constructed")


def _unexpected_scan(**_kwargs: object) -> dict[str, object]:
    raise UnexpectedDatabaseAccess("stale-job query was attempted")


def _unexpected_cleanup(*_args: object, **_kwargs: object) -> object:
    raise UnexpectedDatabaseAccess("guest cleanup was attempted")


def _install_import_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    gateway_factory: Callable[[], object] = _unexpected_gateway,
    stale_scan: Callable[..., dict[str, object]] = _unexpected_scan,
    guest_cleanup_operation: Callable[..., object] = _unexpected_cleanup,
) -> None:
    for name in ("argus", "argus.api", "argus.api.chat", "argus.domain"):
        monkeypatch.setitem(sys.modules, name, _package(name))

    backtest_jobs = ModuleType("argus.api.chat.backtest_jobs")
    backtest_jobs.DEFAULT_STALE_QUEUED_SECONDS = 15 * 60
    backtest_jobs.DEFAULT_STALE_RUNNING_SECONDS = 15 * 60

    backtest_jobs.scan_stale_backtest_jobs = stale_scan
    monkeypatch.setitem(
        sys.modules,
        "argus.api.chat.backtest_jobs",
        backtest_jobs,
    )

    guest_cleanup = ModuleType("argus.domain.guest_cleanup")

    guest_cleanup.cleanup_expired_guest_workspaces = guest_cleanup_operation
    monkeypatch.setitem(sys.modules, "argus.domain.guest_cleanup", guest_cleanup)

    supabase_gateway = ModuleType("argus.domain.supabase_gateway")

    class StubSupabaseGateway:
        @classmethod
        def from_env(cls) -> object:
            return gateway_factory()

    supabase_gateway.SupabaseGateway = StubSupabaseGateway
    monkeypatch.setitem(
        sys.modules,
        "argus.domain.supabase_gateway",
        supabase_gateway,
    )

    dotenv = ModuleType("dotenv")

    def unexpected_dotenv_load() -> bool:
        raise UnexpectedDatabaseAccess("dotenv discovery was attempted")

    dotenv.load_dotenv = unexpected_dotenv_load
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)


def _load_entry_point(
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    *,
    gateway_factory: Callable[[], object] = _unexpected_gateway,
    stale_scan: Callable[..., dict[str, object]] = _unexpected_scan,
    guest_cleanup_operation: Callable[..., object] = _unexpected_cleanup,
) -> ModuleType:
    _install_import_stubs(
        monkeypatch,
        gateway_factory=gateway_factory,
        stale_scan=stale_scan,
        guest_cleanup_operation=guest_cleanup_operation,
    )
    monkeypatch.syspath_prepend(str(OPS_DIR))
    module_name = f"issue_413_{Path(filename).stem}"
    spec = importlib.util.spec_from_file_location(module_name, OPS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


def _clear_connection_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in CONNECTION_ENV:
        monkeypatch.delenv(name, raising=False)


def _set_fake_connection_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://operator:do-not-print@db.issue413.test:5432/argus",
    )
    monkeypatch.setenv("SUPABASE_URL", "https://api.issue413.test")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")


def test_stale_job_reconciliation_refuses_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_connection_environment(monkeypatch)
    entry_point = _load_entry_point(monkeypatch, "stale_backtest_jobs.py")

    with pytest.raises(SystemExit) as exc_info:
        entry_point.main([])

    assert exc_info.value.code == 2
    assert "DATABASE_URL" in capsys.readouterr().err


def test_guest_cleanup_refuses_before_database_access(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_connection_environment(monkeypatch)
    entry_point = _load_entry_point(
        monkeypatch,
        "cleanup_expired_guest_workspaces.py",
    )
    monkeypatch.setattr(sys, "argv", [str(OPS_DIR / entry_point.__name__)])

    with pytest.raises(SystemExit) as exc_info:
        entry_point.main()

    assert exc_info.value.code == 2
    assert "DATABASE_URL" in capsys.readouterr().err


@pytest.mark.parametrize(
    "database_url",
    (
        "not-a-url",
        "https://db.issue413.test/argus",
        "postgresql:///argus",
        "postgresql://db.issue413.test:not-a-port/argus",
    ),
)
def test_stale_job_reconciliation_rejects_invalid_database_targets(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    database_url: str,
) -> None:
    _clear_connection_environment(monkeypatch)
    _set_fake_connection_environment(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", database_url)
    entry_point = _load_entry_point(monkeypatch, "stale_backtest_jobs.py")

    with pytest.raises(SystemExit) as exc_info:
        entry_point.main([])

    assert exc_info.value.code == 2
    assert "DATABASE_URL" in capsys.readouterr().err


def test_stale_job_json_keeps_target_on_stderr_before_gateway_construction(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_connection_environment(monkeypatch)
    _set_fake_connection_environment(monkeypatch)
    output_before_gateway: list[tuple[str, str]] = []

    def gateway_factory() -> object:
        captured = capsys.readouterr()
        output_before_gateway.append((captured.out, captured.err))
        return object()

    def stale_scan(**_kwargs: object) -> dict[str, object]:
        return {"status": "ready"}

    entry_point = _load_entry_point(
        monkeypatch,
        "stale_backtest_jobs.py",
        gateway_factory=gateway_factory,
        stale_scan=stale_scan,
    )

    assert entry_point.main(["--json"]) == 0
    assert output_before_gateway == [
        (
            "",
            "destructive database target: "
            "database_host=db.issue413.test supabase_host=api.issue413.test\n",
        )
    ]
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"status": "ready"}
    assert captured.err == ""
    assert "do-not-print" not in output_before_gateway[0][1]


@dataclass(frozen=True)
class _CleanupResult:
    auth_delete_failed: int = 0
    purge_failed: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "auth_delete_failed": self.auth_delete_failed,
            "purge_failed": self.purge_failed,
        }


def test_guest_cleanup_keeps_json_stdout_clean_and_announces_before_gateway(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _clear_connection_environment(monkeypatch)
    _set_fake_connection_environment(monkeypatch)
    output_before_gateway: list[tuple[str, str]] = []

    def gateway_factory() -> object:
        captured = capsys.readouterr()
        output_before_gateway.append((captured.out, captured.err))
        return object()

    def guest_cleanup_operation(*_args: object, **_kwargs: object) -> object:
        return _CleanupResult()

    entry_point = _load_entry_point(
        monkeypatch,
        "cleanup_expired_guest_workspaces.py",
        gateway_factory=gateway_factory,
        guest_cleanup_operation=guest_cleanup_operation,
    )
    monkeypatch.setattr(sys, "argv", [str(OPS_DIR / entry_point.__name__)])

    assert entry_point.main() == 0
    assert output_before_gateway == [
        (
            "",
            "destructive database target: "
            "database_host=db.issue413.test supabase_host=api.issue413.test\n",
        )
    ]
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "auth_delete_failed": 0,
        "purge_failed": 0,
    }
    assert captured.err == ""
    assert "do-not-print" not in output_before_gateway[0][1]


def test_stale_job_reconciliation_maps_explicit_operator_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_connection_environment(monkeypatch)
    monkeypatch.setenv(
        "ARGUS_WORKFLOW_DATABASE_URL",
        "postgresql://operator:do-not-print@workflow.issue413.test:5432/argus",
    )
    monkeypatch.setenv(
        "ARGUS_STALE_JOBS_SUPABASE_URL",
        "https://stale-api.issue413.test",
    )
    monkeypatch.setenv(
        "ARGUS_STALE_JOBS_SUPABASE_SERVICE_ROLE_KEY",
        "test-service-role-key",
    )
    canonical_environment: list[tuple[str | None, str | None, str | None]] = []

    def gateway_factory() -> object:
        canonical_environment.append(
            (
                os.getenv("DATABASE_URL"),
                os.getenv("SUPABASE_URL"),
                os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            )
        )
        return object()

    def stale_scan(**_kwargs: object) -> dict[str, object]:
        return {"status": "ready"}

    entry_point = _load_entry_point(
        monkeypatch,
        "stale_backtest_jobs.py",
        gateway_factory=gateway_factory,
        stale_scan=stale_scan,
    )

    assert entry_point.main(["--json"]) == 0
    assert canonical_environment == [
        (
            "postgresql://operator:do-not-print@workflow.issue413.test:5432/argus",
            "https://stale-api.issue413.test",
            "test-service-role-key",
        )
    ]


def test_project_url_is_pinned_as_the_announced_gateway_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_connection_environment(monkeypatch)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://operator:do-not-print@db.issue413.test:5432/argus",
    )
    monkeypatch.setenv(
        "SUPABASE_PROJECT_URL",
        "https://project-api.issue413.test",
    )
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    supabase_url_at_gateway: list[str | None] = []

    def gateway_factory() -> object:
        supabase_url_at_gateway.append(os.getenv("SUPABASE_URL"))
        return object()

    def stale_scan(**_kwargs: object) -> dict[str, object]:
        return {"status": "ready"}

    entry_point = _load_entry_point(
        monkeypatch,
        "stale_backtest_jobs.py",
        gateway_factory=gateway_factory,
        stale_scan=stale_scan,
    )

    assert entry_point.main(["--json"]) == 0
    assert supabase_url_at_gateway == ["https://project-api.issue413.test"]


def test_stale_job_wrapper_does_not_load_repository_dotenv(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    github_dir = checkout / ".github"
    bin_dir = checkout / "bin"
    github_dir.mkdir(parents=True)
    bin_dir.mkdir()
    shutil.copy2(REPO_ROOT / ".github/stale-backtest-jobs.sh", github_dir)
    shutil.copy2(REPO_ROOT / ".github/argus-env.sh", github_dir)
    (checkout / ".env").write_text(
        "DATABASE_URL=postgresql://dotenv.issue413.test/argus\n"
        "ARGUS_STALE_JOBS_SUPABASE_URL=https://dotenv-api.issue413.test\n"
        "ARGUS_STALE_JOBS_SUPABASE_SERVICE_ROLE_KEY=dotenv-service-role-key\n"
    )
    poetry_stub = bin_dir / "poetry"
    poetry_stub.write_text(
        "#!/bin/sh\n"
        "printf 'database=%s\\n' \"${DATABASE_URL:-<unset>}\"\n"
        "printf 'supabase=%s\\n' \"${SUPABASE_URL:-<unset>}\"\n"
        "printf 'service_key=%s\\n' \"${SUPABASE_SERVICE_ROLE_KEY:-<unset>}\"\n"
    )
    poetry_stub.chmod(0o755)
    environment = os.environ.copy()
    for name in CONNECTION_ENV:
        environment.pop(name, None)
    environment["PATH"] = f"{bin_dir}{os.pathsep}{environment['PATH']}"

    result = subprocess.run(
        [str(github_dir / "stale-backtest-jobs.sh"), "--json"],
        cwd=checkout,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == (
        "database=<unset>\n" "supabase=<unset>\n" "service_key=<unset>\n"
    )
    assert result.stderr == ""
