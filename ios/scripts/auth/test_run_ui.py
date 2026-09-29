"""Local response-loss injection requires a deliberate launcher opt-in."""

import json
import plistlib
import runpy
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import local_stack


@pytest.mark.parametrize("enabled", [False, True])
def test_response_loss_is_explicit_runner_opt_in(tmp_path, monkeypatch, enabled):
    script = tmp_path / "ios/scripts/auth/run-ui.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).with_name("run-ui.py"), script)
    monkeypatch.setattr(local_stack, "ROOT", tmp_path)
    work = tmp_path / "ios/.build/accounts-local-58500"
    work.mkdir(parents=True)
    work.joinpath("client.json").write_text(
        json.dumps(
            {
                "apiURL": "http://127.0.0.1:58500/api/v1",
                "supabaseURL": "http://127.0.0.1:58501",
                "users": [
                    {"email": "a@example.invalid", "password": "synthetic-a"},
                    {"email": "b@example.invalid", "password": "synthetic-b"},
                ],
            }
        )
    )
    observed = []

    def run(command, **kwargs):
        if command[1] == "build-for-testing":
            products = tmp_path / "ios/.build/DerivedData-58500/Build/Products"
            products.mkdir(parents=True)
            products.joinpath("ArgusFoundation_fixture.xctestrun").write_bytes(
                plistlib.dumps({"UITests": {"EnvironmentVariables": {}}})
            )
        else:
            runner = Path(command[command.index("-xctestrun") + 1])
            environment = plistlib.loads(runner.read_bytes())["UITests"][
                "EnvironmentVariables"
            ]
            observed.append(environment["ARGUS_TEST_RESPONSE_LOSS_PROXY"])
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("subprocess.run", run)
    args = [str(script), "owned-simulator", "--accounts", "--port-base", "58500"]
    monkeypatch.setattr(
        sys, "argv", args + (["--response-loss-proxy"] if enabled else [])
    )
    with pytest.raises(SystemExit) as exit:
        runpy.run_path(str(script), run_name="__main__")
    assert exit.value.code == 0
    assert observed == [str(enabled).lower()]
