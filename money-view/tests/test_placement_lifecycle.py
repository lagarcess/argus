"""A delayed interpretation cannot recreate private deposit inputs after clearing."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.fixtures import get_examples
from server.interpreter import Interpretation
from server.models import PlacementInputs
from server.platform.identity import DEMO_PASSWORD
from server.platform.runtime import model_admission


@pytest.mark.parametrize(
    "operation,user,household,status,code",
    [
        ("reset", "user-demo", "household-demo", 409, "household_data_changed"),
        ("delete", "user-other", "household-other", 401, "authentication_required"),
        ("demote", "user-partner", "household-demo", 409, "household_access_changed"),
    ],
)
def test_delayed_confirmation_cannot_outlive_household_authority(
    tmp_path, operation, user, household, status, code
):
    entered, resume = Event(), Event()
    inputs = PlacementInputs.model_validate(get_examples()[0]["inputs"])

    class ControlledInterpreter:
        mode = "fixture_and_model"

        async def interpret(self, *args, admission, **kwargs):
            async with model_admission(*admission):
                entered.set()
                assert await asyncio.to_thread(resume.wait, 5)
                return Interpretation(status="confirmation", inputs=inputs)

    app = create_app(tmp_path / "placement-lifecycle.sqlite3", ControlledInterpreter())
    with TestClient(app) as first:
        second = TestClient(app)
        actor = "user-demo" if operation == "demote" else user
        try:
            for client, login in ((first, user), (second, actor)):
                response = client.post(
                    "/api/platform/session/login",
                    json={"user_id": login, "password": DEMO_PASSWORD},
                )
                assert response.status_code == 200
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(
                    first.post,
                    "/api/interpret",
                    json={"message": "Synthetic private deposit input", "locale": "en"},
                )
                try:
                    assert entered.wait(5)
                    if operation == "reset":
                        changed = second.post(
                            "/api/platform/settings/data/reset",
                            json={"confirmation": "RESET THIS HOUSEHOLD"},
                        )
                    elif operation == "delete":
                        changed = second.request(
                            "DELETE",
                            "/api/platform/settings/account",
                            json={
                                "confirmation": "DELETE MY LOCAL ACCOUNT",
                                "current_password": DEMO_PASSWORD,
                            },
                        )
                    else:
                        changed = second.patch(
                            f"/api/platform/household/members/{user}",
                            json={"role": "viewer"},
                        )
                    assert changed.status_code == 200, changed.text
                finally:
                    resume.set()
                response = pending.result(timeout=10)
            assert response.status_code == status, response.text
            assert response.json() == {"code": code}
            with app.state.store.connection() as db:
                for table in ("p_placement_confirmations", "p_runtime_model_leases"):
                    assert (
                        db.execute(
                            f"SELECT COUNT(*) FROM {table} WHERE household_id=?",
                            (household,),
                        ).fetchone()[0]
                        == 0
                    )
                assert db.execute("SELECT COUNT(*) FROM confirmations").fetchone()[0] == 0
            if operation == "reset":
                fresh = first.post(
                    "/api/confirmations", json={"inputs": inputs.model_dump(mode="json")}
                )
                assert fresh.status_code == 200, fresh.text
        finally:
            second.close()
