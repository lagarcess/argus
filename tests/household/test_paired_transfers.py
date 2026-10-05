import json
from datetime import timedelta

import pytest
from argus.domain.household.errors import HouseholdNotFound
from argus.domain.household.financial import HouseholdFinancialService
from argus.domain.recording.money_schemas import MoneyRequest

from tests.household.financial_fixtures import (
    DSN,
    NOW,
    account,
    command,
    key,
    money,
    reviewed,
    setup,
    share,
)

pytestmark = pytest.mark.skipif(not DSN, reason="Disposable PostgreSQL required")


def test_household_pair_retry_and_revoked_source_are_currency_safe(lane, monkeypatch):
    monkeypatch.setenv("ARGUS_CROSS_CURRENCY_TRANSFERS_ENABLED", "true")
    service, records, (a, b, _) = lane
    hid, mid, _ = setup(lane)
    source, dest = (
        account(records, a, currency="USD"),
        account(records, a, currency="DOP"),
    )
    share(service, a, hid, source, mid, "edit")
    share(service, a, hid, dest, mid, "edit")
    body = MoneyRequest(
        kind="transfer",
        source_account_id=source,
        destination_account_id=dest,
        amount="1",
        destination_amount="60",
        occurred_at=NOW - timedelta(days=1),
    )
    body = reviewed(service, a, hid, body)
    operation = key()
    saved = money(service, a, hid, body, k=operation)
    assert money(service, a, hid, body, k=operation)["replayed"]
    aid = saved["activity"]["activity"]["activity_id"]
    command(
        service,
        a,
        "withdraw:" + source,
        lambda: service.replace_grants(
            user_id=a, household_id=hid, account_id=source, recipients=[]
        ),
        hid,
    )
    reader = HouseholdFinancialService(service)
    view = reader.detail(b, hid, dest)["activities"][0]
    assert view["private_counterpart"] and not view["can_edit"]
    assert view["activity"]["currency"] == "DOP"
    assert view["activity"]["amount_minor"] is None
    assert view["activity"]["legs"][0]["amount_minor"] == 6000
    encoded = json.dumps([view, reader.history(b, hid, aid)], default=str)
    assert source not in encoded and '"USD"' not in encoded
    denied = body.model_copy(
        update={
            "expected_revision": 1,
            "expected_versions": {},
            "preview_token": None,
            "reason": "Denied correction",
        }
    )
    with pytest.raises(HouseholdNotFound):
        money(service, b, hid, denied, aid=aid)
    assert records.get_account(user_id=a, account_id=dest).account.version == 2
