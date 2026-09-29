"""Isolation guards for independently runnable native demonstrations."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import local_stack
import pytest
from local_stack import Allocation


@pytest.mark.parametrize(
    "accounts,project,state",
    [(False, "ios-auth-8be2", "auth-local"), (True, "ios-accounts", "accounts-local")],
)
def test_defaults_preserve_existing_stack(accounts, project, state):
    allocation = Allocation(accounts)
    assert allocation.project == project
    assert allocation.work.name == state
    assert allocation.url() == "http://127.0.0.1:58400"
    assert allocation.web_port == 3001


@pytest.mark.parametrize("base", [0, 1023, 65525, 70000])
def test_reject_invalid_port_ranges(base):
    with pytest.raises(ValueError):
        Allocation(True, base)


@pytest.fixture
def allocation(tmp_path, monkeypatch):
    monkeypatch.setattr(local_stack.socket, "socket", MagicMock())
    monkeypatch.setattr(local_stack, "ROOT", tmp_path)
    allocation = Allocation(True, 58500)
    monkeypatch.setattr(local_stack, "ALLOCATION", allocation)
    source = tmp_path / "supabase"
    source.mkdir()
    (source / "migrations").mkdir()
    (source / "seed.sql").write_text("")
    template = ['project_id = "original"']
    sections = {}
    for (section, key), port in allocation.ports.items():
        sections.setdefault(section, []).append(f"{key} = {port}")
    for section, values in sections.items():
        template += [f"[{section}]", *values]
    template += [
        "[auth]",
        'site_url = "http://localhost:3001"',
        "additional_redirect_urls = [",
        "]",
    ]
    (source / "config.toml").write_text("\n".join(template))
    local_stack.configure(accounts=True)
    return allocation


def test_configuration_keeps_project_state_and_ports_together(allocation):
    allocation.verify()
    assert allocation.project == "ios-accounts-58500"
    assert allocation.work.name == "accounts-local-58500"
    assert allocation.web_url == "http://127.0.0.1:58506"
    with pytest.raises(SystemExit, match="Configuration exists"):
        local_stack.configure(accounts=True)


@pytest.mark.parametrize(
    "old,new", [("ios-accounts-58500", "ios-accounts"), ("port = 58502", "port = 58402")]
)
def test_wrong_stack_is_rejected_before_cli_invocation(allocation, monkeypatch, old, new):
    config = allocation.stack / "supabase/config.toml"
    config.write_text(config.read_text().replace(old, new))
    monkeypatch.setattr(
        local_stack.subprocess, "run", lambda *a, **k: pytest.fail("CLI must not run")
    )
    with pytest.raises(SystemExit, match="mismatch"):
        local_stack.sb("stop")


@pytest.mark.parametrize(
    "api,database,accepted",
    [
        (
            "http://127.0.0.1:58501",
            "postgresql://user:secret@127.0.0.1:58502/postgres",
            True,
        ),
        (
            "https://example.invalid",
            "postgresql://user:secret@127.0.0.1:58502/postgres",
            False,
        ),
        (
            "http://127.0.0.1:58501",
            "postgresql://user:secret@127.0.0.1:58402/postgres",
            False,
        ),
        (
            "http://127.0.0.1:58501",
            "postgresql://user:secret@example.invalid:58502/postgres",
            False,
        ),
    ],
)
def test_status_accepts_only_owned_loopback_endpoints(
    allocation, monkeypatch, api, database, accepted
):
    result = {"API_URL": api, "DB_URL": database}
    monkeypatch.setattr(
        local_stack, "sb", lambda *a: SimpleNamespace(stdout=json.dumps(result))
    )
    if accepted:
        assert local_stack.status() == result
    else:
        with pytest.raises(SystemExit, match="non-lane"):
            local_stack.status()


def test_occupied_ports_do_not_create_configuration(tmp_path, monkeypatch):
    allocation = Allocation(True, 58500)
    monkeypatch.setattr(local_stack, "ROOT", tmp_path)
    monkeypatch.setattr(local_stack, "ALLOCATION", allocation)
    socket = MagicMock()
    socket.return_value.__enter__.return_value.bind.side_effect = OSError("occupied")
    monkeypatch.setattr(local_stack.socket, "socket", socket)
    with pytest.raises(SystemExit, match="occupied"):
        local_stack.configure(accounts=True)
    assert not allocation.stack.exists()
