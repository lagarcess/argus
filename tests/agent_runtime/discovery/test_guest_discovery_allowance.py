from __future__ import annotations

import pytest
from argus.api.chat import discovery_evidence
from argus.api.chat.discovery_evidence import (
    discovery_counter_subject,
    discovery_usage_limits,
)
from argus.domain.usage_limits import (
    GLOBAL_DISCOVERY_CEILING_SUBJECT,
    GUEST_DISCOVERY_ALLOWANCE,
    global_discovery_daily_ceiling,
)


class TestAllowanceResolvesByAccountClass:
    def test_a_guest_gets_the_guest_allowance(self) -> None:
        assert discovery_usage_limits(is_guest=True) == [
            ("day", GUEST_DISCOVERY_ALLOWANCE)
        ]

    def test_a_registered_account_keeps_its_own_limits(self) -> None:
        limits = discovery_usage_limits(is_guest=False)
        assert [period for period, _ in limits] == ["hour", "day"]
        assert limits != discovery_usage_limits(is_guest=True)

    def test_the_guest_window_is_a_day_not_a_workspace_session(self) -> None:
        """guest_session anchors to workspace expiry, which renewal moves.

        A day window is what makes the allowance survive a renewed workspace.
        """
        assert [period for period, _ in discovery_usage_limits(is_guest=True)] == [
            "day"
        ]


class TestCounterSubject:
    def test_a_registered_account_is_charged_as_itself(self) -> None:
        assert (
            discovery_counter_subject(
                user_id="user-1", is_guest=False, client_identity="203.0.113.7"
            )
            == "user-1"
        )

    def test_a_guest_is_charged_against_the_visitor_not_the_workspace(self) -> None:
        first = discovery_counter_subject(
            user_id="guest-workspace-1", is_guest=True, client_identity="203.0.113.7"
        )
        renewed = discovery_counter_subject(
            user_id="guest-workspace-2", is_guest=True, client_identity="203.0.113.7"
        )
        # The whole point: a renewed workspace is a new user_id but the same
        # visitor, so the allowance must not reset.
        assert first == renewed
        assert "guest-workspace" not in first

    def test_different_visitors_are_charged_separately(self) -> None:
        assert discovery_counter_subject(
            user_id="g1", is_guest=True, client_identity="203.0.113.7"
        ) != discovery_counter_subject(
            user_id="g1", is_guest=True, client_identity="198.51.100.4"
        )

    @pytest.mark.parametrize("identity", [None, "", "   "])
    def test_unknown_visitor_fails_closed_to_one_shared_bucket(
        self, identity: str | None
    ) -> None:
        """An unmetered allowance is the worse failure."""
        subject = discovery_counter_subject(
            user_id="guest-1", is_guest=True, client_identity=identity
        )
        assert subject.endswith("unknown")
        assert subject != "guest-1"


class TestGlobalCeiling:
    def test_the_ceiling_stops_discovery_before_any_provider_call(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The bound that still holds when someone rotates identity."""
        seen: list[str] = []

        def _within(*, subject: str, limits: list[tuple[str, int]], now: object) -> bool:
            seen.append(subject)
            return subject != GLOBAL_DISCOVERY_CEILING_SUBJECT

        monkeypatch.setattr(discovery_evidence, "_subject_within_limits", _within)
        assert (
            discovery_evidence.discovery_allowance_available(
                "user-1", is_guest=False, client_identity="203.0.113.7"
            )
            is False
        )
        # Checked first, and the per-subject read never happens once it trips.
        assert seen == [GLOBAL_DISCOVERY_CEILING_SUBJECT]

    def test_within_the_ceiling_the_per_subject_allowance_decides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []

        def _within(*, subject: str, limits: list[tuple[str, int]], now: object) -> bool:
            seen.append(subject)
            return True

        monkeypatch.setattr(discovery_evidence, "_subject_within_limits", _within)
        assert (
            discovery_evidence.discovery_allowance_available(
                "guest-1", is_guest=True, client_identity="203.0.113.7"
            )
            is True
        )
        assert seen[0] == GLOBAL_DISCOVERY_CEILING_SUBJECT
        assert seen[1].endswith("203.0.113.7")


class TestCeilingIsConfigurable:
    def test_the_ceiling_can_be_reset_without_a_deploy(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ARGUS_DISCOVERY_GLOBAL_DAILY_CEILING", "7")
        assert global_discovery_daily_ceiling() == 7

    @pytest.mark.parametrize("bad", ["", "   ", "nonsense", "0", "-5"])
    def test_a_bad_override_falls_back_rather_than_disabling_the_breaker(
        self, monkeypatch: pytest.MonkeyPatch, bad: str
    ) -> None:
        monkeypatch.setenv("ARGUS_DISCOVERY_GLOBAL_DAILY_CEILING", bad)
        assert global_discovery_daily_ceiling() > 0
