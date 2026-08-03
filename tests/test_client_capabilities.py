from argus.api.client_capabilities import (
    DOSSIER_DECISION_CONVERSION_CAPABILITY,
    dossier_decision_action_availability,
)


def test_decision_projection_combines_server_truth_with_client_support() -> None:
    assert (
        dossier_decision_action_availability(
            can_save_decision=True,
            raw_client_capabilities=None,
        )
        == "available"
    )
    assert (
        dossier_decision_action_availability(
            can_save_decision=False,
            raw_client_capabilities=None,
        )
        is None
    )
    assert (
        dossier_decision_action_availability(
            can_save_decision=False,
            raw_client_capabilities="unknown_v1",
        )
        is None
    )
    assert (
        dossier_decision_action_availability(
            can_save_decision=False,
            raw_client_capabilities=(
                f"unknown_v1, {DOSSIER_DECISION_CONVERSION_CAPABILITY}"
            ),
        )
        == "account_conversion_required"
    )


def test_oversized_client_capability_signal_fails_closed() -> None:
    assert (
        dossier_decision_action_availability(
            can_save_decision=False,
            raw_client_capabilities=(
                f"{DOSSIER_DECISION_CONVERSION_CAPABILITY}," + "x" * 1024
            ),
        )
        is None
    )
