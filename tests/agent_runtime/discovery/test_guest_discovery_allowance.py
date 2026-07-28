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
        # Opaque text, not a uuid: it keys visitor_usage_counters, which has no
        # foreign key to profiles precisely because a visitor has no account.
        assert first.startswith("visitor:")

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
        assert subject != "guest-1"
        assert subject.startswith("visitor:")
        # The identifier itself is never stored, even the placeholder.
        assert "unknown" not in subject


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
        monkeypatch.setattr(
            discovery_evidence, "_global_ceiling_available", lambda *, now: False
        )
        assert (
            discovery_evidence.discovery_allowance_available(
                "user-1", is_guest=False, client_identity="203.0.113.7"
            )
            is False
        )
        # The per-subject read never happens once the ceiling trips.
        assert seen == []

    def test_within_the_ceiling_the_per_subject_allowance_decides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []

        def _within(*, subject: str, limits: list[tuple[str, int]], now: object) -> bool:
            seen.append(subject)
            return True

        # Hermetic against ambient env: a worktree .env with supabase
        # persistence would otherwise route the guest read to the real
        # visitor table instead of the mocked memory path.
        monkeypatch.setattr(discovery_evidence.api_state, "supabase_gateway", None)
        monkeypatch.setattr(discovery_evidence, "_subject_within_limits", _within)
        monkeypatch.setattr(
            discovery_evidence, "_global_ceiling_available", lambda *, now: True
        )
        assert (
            discovery_evidence.discovery_allowance_available(
                "guest-1", is_guest=True, client_identity="203.0.113.7"
            )
            is True
        )
        assert seen[0].startswith("visitor:")
        # A raw address is never the stored key.
        assert "203.0.113.7" not in seen[0]


class TestChargeRule:
    """Spec §4.3: two bounds, two rules. The global ceiling counts every
    attempt because failed provider calls can still be billed; the user's
    allowance is charged only for a usable result."""

    def _record(
        self, monkeypatch: pytest.MonkeyPatch, usage: dict
    ) -> tuple[list[str], list[str]]:
        ceiling_calls: list[str] = []
        subject_calls: list[str] = []
        monkeypatch.setattr(
            discovery_evidence,
            "_charge_global_ceiling",
            lambda: ceiling_calls.append("ceiling"),
        )
        monkeypatch.setattr(
            discovery_evidence,
            "_charge_discovery_attempt",
            lambda **kwargs: subject_calls.append(kwargs["user_id"]),
        )
        monkeypatch.setattr(
            discovery_evidence,
            "_append_research_ledger_row",
            lambda **kwargs: None,
        )
        discovery_evidence.record_discovery_search_evidence(
            usage=usage,
            user_id="user-1",
            conversation_id=None,
            message_id=None,
            request_id=None,
        )
        return ceiling_calls, subject_calls

    def test_a_usable_result_charges_both_bounds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ceiling, subject = self._record(
            monkeypatch, {"search_attempted": True, "result_count": 5}
        )
        assert ceiling == ["ceiling"]
        assert subject == ["user-1"]

    def test_a_failed_attempt_charges_the_ceiling_but_not_the_user(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ceiling, subject = self._record(
            monkeypatch,
            {"search_attempted": True, "fallback_code": "search_timeout"},
        )
        assert ceiling == ["ceiling"]
        assert subject == []

    def test_no_attempt_charges_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ceiling, subject = self._record(monkeypatch, {"search_attempted": False})
        assert ceiling == []
        assert subject == []


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
