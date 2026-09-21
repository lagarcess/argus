from decimal import Decimal

import pytest
from server.fixtures import get_examples
from server.models import PlacementInputs
from server.platform.common import Context
from server.platform.deposits import clear_data, export_data
from server.providers import FixtureProvider
from server.service import PlacementService, ServiceError
from server.store import Store


@pytest.fixture
def households(tmp_path):
    store = Store(tmp_path / "households.sqlite3")
    owner = PlacementService(store, "household-demo")
    owner.bootstrap()
    return store, owner, PlacementService(store, "household-other")


def saved(service, amount):
    inputs = PlacementInputs.model_validate(get_examples()[0]["inputs"]).model_copy(
        update={"amount": Decimal(amount)}
    )
    confirmation = service.create_confirmation(inputs)
    result = service.compute(confirmation["id"], inputs)
    decision = service.save(result["id"])
    return inputs, confirmation, result, decision


def test_placement_receipts_and_notifications_are_household_scoped(households):
    store, owner, other = households
    inputs, confirmation, result, decision = saved(owner, "125000")
    _, _, other_result, other_decision = saved(other, "42000")
    for method, arguments in [
        (other.compute, (confirmation["id"], inputs)),
        (other.save, (result["id"],)),
        (other.decision, (decision["id"],)),
    ]:
        with pytest.raises(ServiceError) as failure:
            method(*arguments)
        assert failure.value.status == 404
    assert [item["id"] for item in other.home("fixture")["saved"]] == [
        other_decision["id"]
    ]
    load_id = owner.begin_load("leader_changed")
    owner.finish_load(load_id, FixtureProvider("leader_changed"))
    own_notice = owner.notices()["items"][0]
    assert own_notice["decision_id"] == decision["id"]
    assert other.notices()["items"][0]["decision_id"] == other_decision["id"]
    with pytest.raises(ServiceError) as failure:
        other.read_notice(own_notice["id"])
    assert failure.value.status == 404
    # Ownership of new comparisons follows each saved answer through a global load.
    with store.connection() as db:
        household = db.execute(
            "SELECT household_id FROM p_placement_comparisons WHERE id=?",
            (other.decision(other_decision["id"])["latest"]["id"],),
        ).fetchone()[0]
    assert household == "household-other"
    assert other_result["inputs"]["amount"] == "42000.00"


def test_export_and_reset_only_remove_current_household_receipts(households):
    store, owner, other = households
    saved(owner, "125000")
    _, _, _, preserved = saved(other, "42000")
    context = Context("user-demo", "household-demo", "owner", "session")
    with store.connection(write=True) as db:
        exported = export_data(db, context)
        assert len(exported["comparisons"]) == 1
        clear_data(db, context)
        assert export_data(db, context)["comparisons"] == []
    assert owner.home("fixture")["saved"] == []
    assert other.decision(preserved["id"]) == preserved
    assert owner.home("fixture")["source_status"]["state"] == "ready"
    # Reopening the store never reassigns or recreates deleted private artifacts.
    assert PlacementService(Store(store.path)).home("fixture")["saved"] == []
