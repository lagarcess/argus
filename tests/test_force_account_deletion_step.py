"""The operator-only force-complete entry point (Lane 6)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from argus.domain.account_deletion.service import (
    AccountDeletionIncomplete,
    AccountDeletionRejected,
    DeletionOutcome,
)

from scripts.ops import force_account_deletion_step as force

ENV = {
    "DATABASE_URL": "postgresql://ops@db.example.supabase.co:5432/postgres",
    "SUPABASE_URL": "https://example.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role",
}
USER = "00000000-0000-4000-8000-000000000001"
ARGS = ["--user-id", USER, "--step", "apple", "--operator", "lucas"]


@pytest.fixture
def service(monkeypatch):  # noqa: ANN001, ANN201
    from argus.api import account_deletion_runtime
    from argus.domain import supabase_gateway

    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    built = MagicMock()
    monkeypatch.setattr(account_deletion_runtime, "build_service", lambda **_: built)
    monkeypatch.setattr(
        supabase_gateway.SupabaseGateway, "from_env", classmethod(lambda cls: MagicMock())
    )
    return built


def test_forces_the_step_then_resumes_the_run(service, capsys) -> None:  # noqa: ANN001
    service.delete_account.return_value = DeletionOutcome(status="done", counts={})
    assert force.main([*ARGS, "--reason", "Apple invalid_request for 7 days"]) == 0
    service.force_complete_step.assert_called_once_with(
        user_id=USER,
        step="apple",
        reason="Apple invalid_request for 7 days",
        operator="lucas",
    )
    service.delete_account.assert_called_once_with(user_id=USER)
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1]) == {
        "forced": True,
        "status": "done",
    }


def test_still_pending_elsewhere_is_reported(service, capsys) -> None:  # noqa: ANN001
    service.delete_account.side_effect = AccountDeletionIncomplete(
        "third_party_pending", ["plaid"]
    )
    assert force.main([*ARGS, "--reason", "app removed"]) == 0
    assert json.loads(capsys.readouterr().out.strip().splitlines()[-1])["pending"] == [
        "plaid"
    ]


def test_refuses_an_email_in_the_reason_and_unknown_steps(service) -> None:  # noqa: ANN001
    with pytest.raises(SystemExit) as exited:
        force.main([*ARGS, "--reason", "asked by someone@example.com"])
    assert exited.value.code == 2
    with pytest.raises(SystemExit):
        force.main(
            ["--user-id", USER, "--step", "storage", "--operator", "x", "--reason", "y"]
        )
    service.force_complete_step.assert_not_called()


def test_no_run_waiting_is_a_failure(service, capsys) -> None:  # noqa: ANN001
    service.force_complete_step.side_effect = AccountDeletionRejected(
        "no_run_awaiting_third_parties"
    )
    assert force.main([*ARGS, "--reason", "app removed"]) == 1
    service.delete_account.assert_not_called()
