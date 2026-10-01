"""Guard real local verification resources and exact recovery bytes."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

SPEC = importlib.util.spec_from_file_location(
    "shared_plans_journey", Path(__file__).with_name("shared-plans-journey.py")
)
journey = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(journey)


def test_interrupted_operation_resumes_same_actor_bytes_and_key(tmp_path):
    path = tmp_path / "private.json"
    first = journey.Journal(path, create=True)
    calls = []

    def send(*args):
        calls.append(args)
        if len(calls) == 1:
            raise journey.Refused("committed response interrupted")
        return 200, {"replayed": True, "membership_id": "same-incarnation"}

    client = Mock(api=Mock(side_effect=send))
    with pytest.raises(journey.Refused):
        first.command(
            client,
            "accept",
            1,
            "/household-invitations/accept",
            lambda: {"token": "synthetic-invitation"},
        )
    resumed = journey.Journal(path)
    rebuild = Mock(side_effect=AssertionError("Must retain original command"))
    result = resumed.command(client, "accept", 0, "/households", rebuild)
    assert calls[0] == calls[1]
    assert calls[1][0] == 1
    assert json.loads(calls[1][3]) == {"token": "synthetic-invitation"}
    assert result == {"replayed": True, "membership_id": "same-incarnation"}
    rebuild.assert_not_called()
    assert path.stat().st_mode & 0o777 == 0o600
    accepted = journey.Journal(path)
    assert accepted.command(client, "accept", 2, "/households", rebuild) == result
    assert len(calls) == 2


@pytest.mark.parametrize(
    "path",
    [
        "https://hosted.invalid/households",
        "/households/../private",
        "/households//private",
        "/households/%2e%2e/private",
        "/chat",
        "//hosted.invalid/households",
    ],
)
def test_unrelated_or_redirect_like_path_refused_before_http(path):
    with pytest.raises(journey.Refused):
        journey.validate_path(path)


def test_pending_write_blocks_new_operation_before_build_or_http(tmp_path):
    journal = journey.Journal(tmp_path / "private.json", create=True)
    client = Mock(api=Mock(side_effect=journey.Refused("lost")))
    with pytest.raises(journey.Refused):
        journal.command(client, "first", 0, "/households", lambda: {"name": "Casa"})
    builder = Mock()
    with pytest.raises(journey.Refused, match="Resume pending"):
        journal.command(client, "second", 1, "/households", builder)
    builder.assert_not_called()
    assert client.api.call_count == 1


@pytest.mark.parametrize(
    "origin,count", [("https://hosted.invalid/api/v1", 3), (journey.API, 2)]
)
def test_wrong_environment_or_missing_third_identity_refused(
    tmp_path, monkeypatch, origin, count
):
    monkeypatch.setattr(journey, "WORK", tmp_path)
    path = tmp_path / "client.json"
    path.write_text(
        json.dumps({"apiURL": origin, "supabaseURL": journey.AUTH, "users": [{}] * count})
    )
    path.chmod(0o600)
    with pytest.raises(journey.Refused):
        journey.load_client()
