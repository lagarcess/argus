from tests.financial_recording import scenarios


def test_both_legs_of_a_transfer_change_and_vanish_together():
    assert scenarios.linked_correction_and_removal() == {
        "recorded": [900_000, 100_000, 0],
        "amount_corrected": [850_000, 150_000, 0],
        "counter_corrected": [850_000, 0, 150_000],
        "stale_correction": "StaleVersion",
        "after_stale": [850_000, 0, 150_000],
        "removed": [1_000_000, 0, 0],
        "history": [
            [100_000, "acct-3", None, False],
            [150_000, "acct-3", "amount was 1,500", False],
            [150_000, "acct-5", "went to Meta", False],
            [150_000, "acct-5", "never happened", True],
        ],
        "versions": [5, 4, 3],
    }
