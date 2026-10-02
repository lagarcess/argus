"""A native launcher must never select another lane's device or fixture."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from shared_plan_scene import SIMULATOR, shared_scene


def scene(tmp_path):
    rows = {
        "household": {
            "result": {"household_id": str(uuid4()), "membership_id": str(uuid4())}
        },
        "accept": {"result": {"membership_id": str(uuid4())}},
    }
    for actor, kinds in (
        (0, ("checking", "savings", "card", "unknown", "usd")),
        (1, ("checking", "savings")),
    ):
        for kind in kinds:
            rows[f"account-{actor}-{kind}"] = {
                "result": {"id": str(uuid4()), "nickname": f"Synthetic {actor} {kind}"}
            }
    rows["invite"] = {"result": {"invitation": {"token": "must-stay-private"}}}
    path = tmp_path / "shared-plans-private.json"
    path.write_text(json.dumps({"version": 1, "suffix": "synthetic", "operations": rows}))
    path.chmod(0o600)
    return path


def arguments(**updates):
    return SimpleNamespace(
        **(
            dict(
                accounts=True,
                port_base=59750,
                api_port=None,
                simulator=SIMULATOR,
                user_index=0,
            )
            | updates
        )
    )


def test_exports_only_public_synthetic_ids_names_and_suffix(tmp_path):
    scene(tmp_path)
    result = shared_scene(arguments(), tmp_path)
    assert result["ARGUS_TEST_SHARED_PLAN_ACCOUNT_B_NAME"] == "Synthetic 1 checking"
    assert result["ARGUS_TEST_SHARED_PLAN_STAMP"] == "synthetic"
    assert "must-stay-private" not in json.dumps(result)
    assert len(result) == 18


@pytest.mark.parametrize(
    "change",
    [
        dict(accounts=False),
        dict(port_base=58700),
        dict(api_port=59762),
        dict(simulator="8AFB6084-8918-416E-9164-E21061306BEC"),
        dict(user_index=1),
    ],
)
def test_other_resource_or_actor_refused_before_fixture_read(tmp_path, change):
    with pytest.raises(SystemExit, match="assigned"):
        shared_scene(arguments(**change), tmp_path)


@pytest.mark.parametrize("unsafe", ["permissions", "symlink", "missing"])
def test_unsafe_private_fixture_refused(tmp_path, unsafe):
    path = scene(tmp_path)
    if unsafe == "permissions":
        path.chmod(0o644)
    elif unsafe == "symlink":
        target = path.with_suffix(".original")
        path.rename(target)
        path.symlink_to(target)
    else:
        path.unlink()
    with pytest.raises(SystemExit, match="safe"):
        shared_scene(arguments(), tmp_path)
