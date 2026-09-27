from tests.financial_recording import scenarios

BLOCKING = "blocking"


def test_equal_amount_alone_is_never_a_match():
    result = scenarios.equal_amount_not_a_match()
    assert result["different_account"] == {}
    assert result["different_day"] == {}
    assert result["same_signature"] == {"possible_duplicate": BLOCKING}
    assert result["confirm_unresolved"] == "ReviewRequired:possible_duplicate"
    assert result["resolved_distinct"] == {"activity_records": 4, "totals": 150_000}
    assert result["resolved_duplicate_of"] == {
        "activity_records": 3,
        "totals": 100_000,
        "confirm_returns": "rec-6",
        "linked_methods": ["chat"],
    }


def test_import_flags_malformed_rows_twins_and_reimports():
    result = scenarios.duplicate_import_vs_twins()
    assert result["first_import_issues"] == {
        "tx-dop-01": {},
        "tx-dop-02": {},
        "tx-dop-03": {"possible_duplicate": BLOCKING},
        "tx-dop-04": {},
        "tx-dop-05": {"counter_account_missing": BLOCKING},
        "tx-usd-01": {},
        "tx-currency": {"currency_unsupported": BLOCKING},
        "tx-date": {"date_invalid": BLOCKING},
        "tx-number": {"amount_invalid": BLOCKING},
        "tx-missing": {"field_missing": BLOCKING},
        "tx-household": {"field_missing": BLOCKING},
    }
    assert result["confirmed_in_batch"] == 5
    first = result["after_first_import"]
    assert first["activity_records"] == 5
    assert [first["totals"]["DOP"]["spending"], first["totals"]["DOP"]["income"]] == [
        22_550,
        120_000,
    ]
    assert result["reimport"] == {
        "rows_already_recorded": [
            "tx-currency",
            "tx-date",
            "tx-dop-01",
            "tx-dop-02",
            "tx-dop-03",
            "tx-dop-04",
            "tx-dop-05",
            "tx-household",
            "tx-missing",
            "tx-number",
            "tx-usd-01",
        ],
        "confirm": "ReviewRequired:already_recorded",
        "activity_records": 5,
    }
    assert result["overlap_issues"] == {
        "tx-dop-01": {"already_recorded": BLOCKING},
        "overlap-new": {},
    }
    assert result["after_overlap"] == {"activity_records": 6, "dop_balance": 591_450}
    dop, usd = result["totals"]["DOP"], result["totals"]["USD"]
    assert [dop["spending"], dop["income"]] == [28_550, 120_000]
    assert [usd["spending"], usd["income"]] == [4000, 0]
