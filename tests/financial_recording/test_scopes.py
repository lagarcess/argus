from datetime import datetime

from tests.financial_recording import scenarios
from tests.financial_recording.derive import DEFAULT_TZ, position
from tests.financial_recording.model import Store

NOW = datetime(2026, 9, 2, 10, tzinfo=DEFAULT_TZ)


def test_position_discloses_unknown_and_archived_accounts():
    result = scenarios.unknown_coverage_disclosure()
    assert result["position"] == {
        "DOP": {
            "assets": 790_000,
            "liabilities": 0,
            "net": 790_000,
            "coverage": {
                "accounts_known": ["acct-1"],
                "accounts_unknown": ["acct-3"],
                "archived_excluded": ["acct-4"],
                "oldest_anchor_as_of": "2026-09-05T18:00:00-04:00",
                "unexplained_gaps": [
                    {
                        "record_id": "rec-9",
                        "account_id": "acct-1",
                        "as_of": "2026-09-05T18:00:00-04:00",
                        "amount": -10_000,
                        "label": "unexplained",
                    }
                ],
            },
        }
    }
    assert result["totals"] == 10_000


def test_revaluation_is_not_income_and_share_weights_asset_and_debt_alike():
    result = scenarios.asset_revaluation_and_share()
    assert result["gaps"] == [[None, None], [-10_000_000, "revaluation"]]
    assert result["totals"]["DOP"]["income"] == 0
    assert result["totals"]["DOP"]["spending"] == 0
    assert result["full"] == {
        "assets": 90_000_000,
        "liabilities": -40_000_000,
        "net": 50_000_000,
    }
    assert result["owner_share"] == {
        "assets": 45_000_000,
        "liabilities": -20_000_000,
        "net": 25_000_000,
    }


def test_owner_share_rounds_once_per_total_not_per_account():
    store = Store(lambda: NOW)
    scope = [
        store.create_account(
            name, "cash", "DOP", "0.01", idempotency_key=name, ownership_share_bps=5000
        ).id
        for name in ("Mitad uno", "Mitad dos")
    ]
    shared = position(store.book, scope, weighting="owner_share")["DOP"]
    assert (shared.assets, shared.net) == (1, 1)


def test_positions_never_sum_across_currencies():
    assert scenarios.multiple_precisions()["positions"] == {
        "DOP": 1000,
        "JPY": 1500,
        "KWD": 1234,
    }
