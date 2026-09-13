"""The pending lifecycle works with a second, test-only artifact layout."""

from __future__ import annotations

import copy
import subprocess
import sys
from dataclasses import dataclass, replace
from types import SimpleNamespace
from typing import Any

import pytest
from argus.domain.pending_artifacts import (
    ACTIVE_ARTIFACT_STATE,
    CONSUMED_ARTIFACT_STATE,
    DEAD_ARTIFACT_STATES,
    DeadPendingArtifactError,
    PendingArtifactLayout,
    PendingArtifactUpdate,
    apply_pending_artifact_update,
    consume_pending_artifact,
    pending_artifact_is_dead,
    restore_pending_artifact,
    stamp_pending_artifact,
)
from faker import Faker

fake = Faker()
LAYOUT = PendingArtifactLayout(
    card_key="review_card",
    card_state_key="review_state",
    reference_key="active_review",
    references_key="review_references",
    reference_type="review",
)


class ConflictError(ValueError):
    pass


@dataclass
class Message:
    id: str
    content: str
    metadata: dict[str, Any]


class MemoryStore:
    def __init__(self, metadata: dict[str, Any]) -> None:
        self.message = Message(fake.uuid4(), fake.sentence(), metadata)
        self.latest_id = self.message.id

    def read(self) -> Message:
        return copy.deepcopy(self.message)

    def write(self, **values: Any) -> Message:
        if values["expected_source_metadata"] != self.message.metadata or (
            values["expected_latest_message_id"] is not None
            and values["expected_latest_message_id"] != self.latest_id
        ):
            raise ConflictError
        assert values["message_id"] == self.message.id
        self.message = replace(
            self.message, content=values["content"], metadata=values["metadata"]
        )
        return self.read()


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore(
        {
            LAYOUT.card_key: {LAYOUT.card_state_key: ACTIVE_ARTIFACT_STATE},
            LAYOUT.reference_key: {"artifact_status": ACTIVE_ARTIFACT_STATE},
            LAYOUT.references_key: [
                {"artifact_type": LAYOUT.reference_type, "artifact_status": "active"},
                {"artifact_type": "unrelated", "artifact_status": "active"},
            ],
            "review_inputs": {"amount": fake.pyint(min_value=1, max_value=1000)},
            "obsolete_sidecar": {"id": fake.uuid4()},
        }
    )


def consume(store: MemoryStore, **overrides: Any) -> str:
    return consume_pending_artifact(
        layout=LAYOUT,
        load=store.read,
        write=store.write,
        conflict_error=ConflictError,
        **overrides,
    )


def restore(store: MemoryStore, **overrides: Any) -> bool:
    return restore_pending_artifact(
        layout=LAYOUT,
        load=store.read,
        write=store.write,
        conflict_error=ConflictError,
        **overrides,
    )


def update(store: MemoryStore, source: Message | None = None, **overrides: Any) -> Any:
    source = source or store.read()
    return apply_pending_artifact_update(
        layout=LAYOUT,
        source_message=source,
        expected_source_metadata=source.metadata,
        expected_latest_message_id=source.id,
        prepare=lambda: PendingArtifactUpdate(
            content="Updated review", metadata={"review_inputs": {"amount": 2000}}
        ),
        write=store.write,
        metadata_extra={"obsolete_sidecar": None},
        **overrides,
    )


@pytest.mark.parametrize("state", sorted(DEAD_ARTIFACT_STATES))
def test_stamp_updates_only_matching_references_without_mutating_source(
    store: MemoryStore, state: str
) -> None:
    before = store.read().metadata
    stamped = stamp_pending_artifact(before, state=state, layout=LAYOUT)
    assert stamped[LAYOUT.card_key][LAYOUT.card_state_key] == state
    assert stamped[LAYOUT.reference_key]["artifact_status"] == state
    assert stamped[LAYOUT.references_key][0]["artifact_status"] == state
    assert stamped[LAYOUT.references_key][1]["artifact_status"] == ACTIVE_ARTIFACT_STATE
    assert before == store.message.metadata
    assert pending_artifact_is_dead(stamped, layout=LAYOUT)


@pytest.mark.parametrize("owner", ["card", "reference"])
def test_either_persisted_state_owner_closes_liveness(
    store: MemoryStore, owner: str
) -> None:
    metadata = store.message.metadata
    if owner == "card":
        metadata[LAYOUT.card_key][LAYOUT.card_state_key] = " CANCELLED "
    else:
        metadata[LAYOUT.reference_key]["artifact_status"] = " Consumed "
    assert pending_artifact_is_dead(metadata, layout=LAYOUT)
    with pytest.raises(DeadPendingArtifactError):
        update(store)


def test_update_owns_patch_removal_and_projection_after_guarded_write(
    store: MemoryStore,
) -> None:
    projected = []
    result = update(store, after_write=lambda: projected.append(store.read()))
    assert result.id == store.message.id
    assert result.metadata["review_inputs"]["amount"] == 2000
    assert "obsolete_sidecar" not in result.metadata
    assert (
        result.metadata[LAYOUT.card_key][LAYOUT.card_state_key] == ACTIVE_ARTIFACT_STATE
    )
    assert projected == [result]


@pytest.mark.parametrize("race", ["edit", "append", "consume"])
def test_losing_update_preserves_winner_and_does_not_project(
    store: MemoryStore, race: str
) -> None:
    source = store.read()
    if race == "edit":
        store.message.metadata["review_inputs"]["amount"] += 1
    elif race == "append":
        store.latest_id = fake.uuid4()
    else:
        assert consume(store) == "consumed"
    winner = store.read()
    with pytest.raises(ConflictError):
        update(
            store, source=source, after_write=lambda: pytest.fail("lost write projected")
        )
    assert store.read() == winner


def test_consumption_is_idempotent_and_only_consumed_cards_restore(
    store: MemoryStore,
) -> None:
    assert consume(store) == "consumed"
    assert consume(store) == "already_consumed"
    assert restore(store)
    assert not pending_artifact_is_dead(store.message.metadata, layout=LAYOUT)
    assert update(store).metadata["review_inputs"]["amount"] == 2000


@pytest.mark.parametrize(
    "state", sorted(DEAD_ARTIFACT_STATES - {CONSUMED_ARTIFACT_STATE})
)
def test_restoration_never_reopens_a_user_closed_artifact(
    store: MemoryStore, state: str
) -> None:
    store.message.metadata = stamp_pending_artifact(
        store.message.metadata, state=state, layout=LAYOUT
    )
    assert not restore(store)
    assert pending_artifact_is_dead(store.message.metadata, layout=LAYOUT)


def test_consumption_rechecks_eligibility_after_conflict(store: MemoryStore) -> None:
    original = copy.deepcopy(store.message.metadata["review_inputs"])

    def competing_edit(**values: Any) -> Message:
        store.message.metadata["review_inputs"]["amount"] += 1
        return store.write(**values)

    outcome = consume_pending_artifact(
        layout=LAYOUT,
        load=store.read,
        write=competing_edit,
        conflict_error=ConflictError,
        can_consume=lambda metadata: metadata["review_inputs"] == original,
    )
    assert outcome == "stale_artifact"
    assert not pending_artifact_is_dead(store.message.metadata, layout=LAYOUT)


def test_restore_rechecks_cancellation_after_conflict(store: MemoryStore) -> None:
    assert consume(store) == "consumed"

    def concurrent_cancel(**values: Any) -> Message:
        store.message.metadata = stamp_pending_artifact(
            store.message.metadata, state="cancelled", layout=LAYOUT
        )
        return store.write(**values)

    assert not restore_pending_artifact(
        layout=LAYOUT,
        load=store.read,
        write=concurrent_cancel,
        conflict_error=ConflictError,
    )
    assert store.message.metadata[LAYOUT.card_key][LAYOUT.card_state_key] == "cancelled"


def test_unreadable_artifact_preserves_legacy_consumption_and_closed_restore() -> None:
    callbacks = dict(
        layout=LAYOUT,
        load=lambda: None,
        write=lambda **_: pytest.fail("missing artifact was written"),
        conflict_error=ConflictError,
    )
    assert consume_pending_artifact(**callbacks) == "unstamped"
    assert not restore_pending_artifact(**callbacks)


def test_shared_lifecycle_imports_without_runtime_api_or_backtest_catalogs() -> None:
    """A fresh process refuses the old backtest edges instead of stubbing them."""
    probe = """
import importlib.abc
import sys

class RefuseBacktestImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith((
            'argus.agent_runtime', 'argus.api', 'argus.strategies',
            'argus.domain.backtest',
        )):
            raise AssertionError(f'Backtest edge imported: {fullname}')

sys.meta_path.insert(0, RefuseBacktestImports())
from argus.domain.pending_artifacts import (
    apply_pending_artifact_update, consume_pending_artifact,
    restore_pending_artifact, pending_artifact_is_dead,
)
"""
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_backtest_adapter_keeps_unreadable_gateway_fallback() -> None:
    from argus.api.chat.confirmation_lifecycle import (
        consume_pending_card_for_run,
        restore_pending_card_after_run,
    )

    # An unavailable row requires no writer. Legacy gateways may have no
    # artifact-update capability, so resolving that method must remain lazy.
    context = dict(
        user_id=fake.uuid4(),
        conversation_id=fake.uuid4(),
        message_id=fake.uuid4(),
        gateway=SimpleNamespace(get_message=lambda **_: None),
    )
    assert consume_pending_card_for_run(**context) == "unstamped"
    assert not restore_pending_card_after_run(**context)
