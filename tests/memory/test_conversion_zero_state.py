from __future__ import annotations

from typing import Any

import pytest
from argus.memory.conversion import (
    MemoryConversionMode,
    MemoryConversionPlan,
    MemoryStateDigest,
    plan_guest_conversion,
)
from argus.memory.subject import MemoryAccountKind, MemorySubject
from pydantic import ValidationError

GUEST_ID = "52cd8fdc-5c11-47f4-b1d5-6e2934d237a4"
EXISTING_ACCOUNT_ID = "a32338d9-0c77-46c5-9d31-ebdbd4f185da"
GUEST = MemorySubject(owner_id=GUEST_ID, kind=MemoryAccountKind.GUEST)
LINKED_ACCOUNT = MemorySubject(
    owner_id=GUEST_ID,
    kind=MemoryAccountKind.REGISTERED,
)
EXISTING_ACCOUNT = MemorySubject(
    owner_id=EXISTING_ACCOUNT_ID,
    kind=MemoryAccountKind.REGISTERED,
)
ZERO = MemoryStateDigest()


def test_same_identity_link_starts_at_zero_and_requires_fresh_opt_in() -> None:
    """Catches same-UUID conversion replaying or enabling memory implicitly."""
    plan = plan_guest_conversion(
        mode=MemoryConversionMode.SAME_IDENTITY_LINK,
        source_subject=GUEST,
        source_state=ZERO,
        destination_subject=LINKED_ACCOUNT,
        destination_state=ZERO,
    )

    assert plan == MemoryConversionPlan(
        transfer_memory=False,
        mine_guest_history=False,
        initialize_memory_enabled=False,
        preserve_destination_memory=False,
    )


@pytest.mark.parametrize(
    "field",
    tuple(MemoryStateDigest.model_fields),
)
def test_any_guest_memory_state_fails_conversion_closed(field: str) -> None:
    """Catches one corrupt Guest state field being replayed into an account."""
    source_state = MemoryStateDigest.model_validate({field: 1})

    with pytest.raises(ValueError, match="Guest memory state must be zero"):
        plan_guest_conversion(
            mode=MemoryConversionMode.EXISTING_ACCOUNT_HANDOFF,
            source_subject=GUEST,
            source_state=source_state,
            destination_subject=EXISTING_ACCOUNT,
            destination_state=ZERO,
        )


@pytest.mark.parametrize(
    "field",
    tuple(MemoryStateDigest.model_fields),
)
def test_same_identity_link_rejects_nonzero_destination_state(field: str) -> None:
    """Catches a same-identity link preserving unexplained pre-link memory."""
    destination_state = MemoryStateDigest.model_validate({field: 1})

    with pytest.raises(ValueError, match="initial destination memory state must be zero"):
        plan_guest_conversion(
            mode=MemoryConversionMode.SAME_IDENTITY_LINK,
            source_subject=GUEST,
            source_state=ZERO,
            destination_subject=LINKED_ACCOUNT,
            destination_state=destination_state,
        )


def test_existing_account_handoff_preserves_destination_without_transfer_or_mining() -> (
    None
):
    """Catches handoff overwriting account memory or mining transferred Guest history."""
    destination_state = MemoryStateDigest(
        settings_count=1,
        candidate_count=2,
        record_count=3,
        prompt_history_count=4,
        pending_work_count=5,
        provider_projection_count=6,
    )
    before = destination_state.model_dump()

    plan = plan_guest_conversion(
        mode=MemoryConversionMode.EXISTING_ACCOUNT_HANDOFF,
        source_subject=GUEST,
        source_state=ZERO,
        destination_subject=EXISTING_ACCOUNT,
        destination_state=destination_state,
    )

    assert plan == MemoryConversionPlan(
        transfer_memory=False,
        mine_guest_history=False,
        initialize_memory_enabled=False,
        preserve_destination_memory=True,
    )
    assert destination_state.model_dump() == before


@pytest.mark.parametrize(
    ("mode", "destination"),
    (
        (MemoryConversionMode.SAME_IDENTITY_LINK, EXISTING_ACCOUNT),
        (MemoryConversionMode.EXISTING_ACCOUNT_HANDOFF, LINKED_ACCOUNT),
    ),
)
def test_conversion_mode_enforces_identity_shape(
    mode: MemoryConversionMode,
    destination: MemorySubject,
) -> None:
    """Catches link and handoff modes accepting the opposite identity topology."""
    with pytest.raises(ValueError, match="identity"):
        plan_guest_conversion(
            mode=mode,
            source_subject=GUEST,
            source_state=ZERO,
            destination_subject=destination,
            destination_state=ZERO,
        )


@pytest.mark.parametrize(
    ("source", "destination"),
    (
        (
            MemorySubject(
                owner_id=GUEST_ID,
                kind=MemoryAccountKind.REGISTERED,
            ),
            EXISTING_ACCOUNT,
        ),
        (
            GUEST,
            MemorySubject(
                owner_id=EXISTING_ACCOUNT_ID,
                kind=MemoryAccountKind.GUEST,
            ),
        ),
    ),
)
def test_conversion_requires_guest_source_and_registered_destination(
    source: MemorySubject,
    destination: MemorySubject,
) -> None:
    """Catches conversion planning with an ineligible typed subject boundary."""
    with pytest.raises(
        ValueError, match="source must be Guest|destination must be registered"
    ):
        plan_guest_conversion(
            mode=MemoryConversionMode.EXISTING_ACCOUNT_HANDOFF,
            source_subject=source,
            source_state=ZERO,
            destination_subject=destination,
            destination_state=ZERO,
        )


@pytest.mark.parametrize("field", tuple(MemoryStateDigest.model_fields))
def test_state_digest_rejects_negative_counts(field: str) -> None:
    """Catches malformed precomputed counts bypassing zero-state validation."""
    with pytest.raises(ValidationError):
        MemoryStateDigest.model_validate({field: -1})


@pytest.mark.parametrize("value", (True, 1.0, "1"))
def test_state_digest_requires_strict_integer_counts(value: object) -> None:
    """Catches coerced booleans, floats, or strings masquerading as state counts."""
    with pytest.raises(ValidationError):
        MemoryStateDigest.model_validate({"record_count": value})


def test_conversion_contract_rejects_untyped_or_extra_input() -> None:
    """Catches permissive conversion inputs smuggling unvalidated state."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MemoryStateDigest.model_validate({"record_count": 0, "transcript": "hidden"})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        MemoryConversionPlan.model_validate(
            {
                "transfer_memory": False,
                "mine_guest_history": False,
                "initialize_memory_enabled": False,
                "preserve_destination_memory": False,
                "replay_guest_messages": False,
            }
        )
    with pytest.raises(TypeError, match="MemoryConversionMode"):
        plan_guest_conversion(
            mode="same_identity_link",  # type: ignore[arg-type]
            source_subject=GUEST,
            source_state=ZERO,
            destination_subject=LINKED_ACCOUNT,
            destination_state=ZERO,
        )


def test_conversion_plan_flags_cannot_be_enabled() -> None:
    """Catches a caller constructing a plan that transfers or mines Guest state."""
    for field in (
        "transfer_memory",
        "mine_guest_history",
        "initialize_memory_enabled",
    ):
        payload: dict[str, Any] = {
            "transfer_memory": False,
            "mine_guest_history": False,
            "initialize_memory_enabled": False,
            "preserve_destination_memory": False,
            field: True,
        }
        with pytest.raises(ValidationError):
            MemoryConversionPlan.model_validate(payload)
