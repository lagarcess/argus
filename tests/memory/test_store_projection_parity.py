"""The two stores must agree about projection freshness, sequence by sequence.

Scope note: record deletion and owner reset are not driven here. Postgres
`delete_record` blocks against this fixture, which is a separate question from
projection freshness, and reset needs a claim lifecycle the harness would have
to reimplement. Reset behaviour is covered directly against the deterministic
store instead, where the divergence actually lived.

Four review findings in a row reduced to the same thing: the deterministic
store and the Postgres store disagreeing about when a projection is
authoritative, in a different method each time. Testing one behaviour at a time
kept missing the next one, so this runs identical operation sequences against
both and compares everything observable after every step.

Record ids and the owner differ between the stores, so operations name records
by label and observations are reported by label. Provider refs are values the
harness chooses, so those are compared directly.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

DSN = os.getenv("ARGUS_DISPOSABLE_DATABASE_URL", "").strip()
pytestmark = pytest.mark.skipif(
    not DSN,
    reason="ARGUS_DISPOSABLE_DATABASE_URL is not configured",
)
psycopg = pytest.importorskip("psycopg")

from _parity_fixtures import (  # noqa: E402
    seed_in_memory_records,
    seed_postgres_owner,
    seed_postgres_record,
)
from argus.memory.postgres_store import (  # noqa: E402
    PostgresCanonicalMemoryStore,
)
from argus.memory.store import InMemoryCanonicalMemoryStore  # noqa: E402
from argus.memory.subject import RegisteredMemoryOwner  # noqa: E402
from psycopg_pool import ConnectionPool  # noqa: E402

LABELS = ("alpha", "beta")


class StoreUnderTest:
    """One store, addressed by record label instead of by id."""

    def __init__(
        self,
        name: str,
        store: Any,
        owner: RegisteredMemoryOwner,
        record_ids: dict[str, str],
    ) -> None:
        self.name = name
        self.store = store
        self.owner = owner
        self.record_ids = record_ids

    def observe(self) -> dict[str, Any]:
        """Everything a caller can learn about projection state."""

        settled = self.store.settled_projection_record_ids(self.owner)
        return {
            "settled": sorted(
                label
                for label, record_id in self.record_ids.items()
                if record_id in settled
            ),
            "refs": {
                label: self.store.get_provider_ref(self.owner, record_id)
                for label, record_id in self.record_ids.items()
            },
            "cleanup": {
                label: sorted(
                    target.provider_ref
                    for target in self.store.list_provider_cleanup_targets(
                        self.owner,
                        record_id,
                    )
                )
                for label, record_id in self.record_ids.items()
            },
        }


def set_ref(label: str, ref: str):
    def operation(subject: StoreUnderTest) -> Any:
        return subject.store.set_provider_ref(
            subject.owner,
            subject.record_ids[label],
            ref,
        )

    operation.description = f"set_ref({label}, {ref})"  # type: ignore[attr-defined]
    return operation


def edit(label: str, value: str):
    def operation(subject: StoreUnderTest) -> Any:
        mutation = subject.store.edit_record(
            subject.owner,
            subject.record_ids[label],
            value=value,
            label=None,
        )
        # Mutations carry ids, which differ per store; report the shape only.
        return None if mutation is None else mutation.provider_ref

    operation.description = f"edit({label})"  # type: ignore[attr-defined]
    return operation


def track_cleanup(label: str, ref: str):
    def operation(subject: StoreUnderTest) -> Any:
        return subject.store.track_provider_cleanup_target(
            subject.owner,
            subject.record_ids[label],
            ref,
        )

    operation.description = f"track_cleanup({label}, {ref})"  # type: ignore[attr-defined]
    return operation


def resolve_cleanup(label: str, ref: str):
    def operation(subject: StoreUnderTest) -> Any:
        return subject.store.resolve_provider_cleanup_target(
            subject.owner,
            subject.record_ids[label],
            ref,
        )

    operation.description = f"resolve_cleanup({label}, {ref})"  # type: ignore[attr-defined]
    return operation


@pytest.fixture(scope="module")
def pool() -> Iterator[ConnectionPool]:
    """One pool for the module: a pool per test exhausts connections."""

    connection_pool = ConnectionPool(
        conninfo=DSN,
        kwargs={"autocommit": True},
        min_size=0,
        max_size=4,
        open=True,
        timeout=5,
        name="projection-parity",
    )
    try:
        yield connection_pool
    finally:
        connection_pool.close()


@pytest.fixture
def stores(pool: ConnectionPool) -> Iterator[tuple[StoreUnderTest, StoreUnderTest]]:
    """A fresh owner per test in both stores, so sequences cannot interfere."""

    with psycopg.connect(DSN, autocommit=True) as connection:
        owner_id = seed_postgres_owner(connection)
        record_ids = {
            label: seed_postgres_record(connection, owner_id) for label in LABELS
        }
    memory_store = InMemoryCanonicalMemoryStore()
    memory_owner, memory_record_ids = seed_in_memory_records(memory_store, LABELS)
    try:
        yield (
            StoreUnderTest("in-memory", memory_store, memory_owner, memory_record_ids),
            StoreUnderTest(
                "postgres",
                PostgresCanonicalMemoryStore(pool),
                RegisteredMemoryOwner(owner_id=owner_id),
                record_ids,
            ),
        )
    finally:
        with psycopg.connect(DSN, autocommit=True) as connection:
            connection.execute("set local statement_timeout = '10s'")
            connection.execute(
                "delete from auth.users where id = %s::uuid",
                (owner_id,),
            )


def _apply(operation: Any, subject: StoreUnderTest) -> Any:
    """Run one operation, treating a rejection as part of the answer.

    Both stores must refuse the same things for the same reason, so raised
    errors are compared rather than escaping and ending the sequence.
    """

    try:
        return ("ok", operation(subject))
    except Exception as error:  # noqa: BLE001 - the type is the assertion
        return ("raised", type(error).__name__, str(error))


def assert_parity(
    stores: tuple[StoreUnderTest, StoreUnderTest],
    operations: list[Any],
) -> None:
    """Apply the same sequence to both stores, comparing after every step."""

    memory_subject, postgres_subject = stores
    history: list[str] = []
    assert (
        memory_subject.observe() == postgres_subject.observe()
    ), "stores disagreed before any operation ran"
    for operation in operations:
        history.append(operation.description)
        memory_result = _apply(operation, memory_subject)
        postgres_result = _apply(operation, postgres_subject)
        trail = " -> ".join(history)
        assert memory_result == postgres_result, (
            f"return values diverged after [{trail}]: "
            f"in-memory={memory_result!r} postgres={postgres_result!r}"
        )
        memory_state = memory_subject.observe()
        postgres_state = postgres_subject.observe()
        assert memory_state == postgres_state, (
            f"observable state diverged after [{trail}]: "
            f"in-memory={memory_state!r} postgres={postgres_state!r}"
        )


def test_same_ref_reasserted_after_an_edit(stores) -> None:  # noqa: ANN001
    """The sequence from the seventh finding."""
    assert_parity(
        stores,
        [
            set_ref("alpha", "ref-1"),
            edit("alpha", "superseding text"),
            set_ref("alpha", "ref-1"),
            set_ref("alpha", "ref-1"),
        ],
    )


def test_ref_replacement(stores) -> None:  # noqa: ANN001
    """A replacement must move freshness and queue the superseded ref."""
    assert_parity(
        stores,
        [
            set_ref("alpha", "ref-1"),
            set_ref("alpha", "ref-2"),
            edit("alpha", "superseding text"),
            set_ref("alpha", "ref-3"),
        ],
    )


def test_edits_interleaved_with_cleanup_reservations(stores) -> None:  # noqa: ANN001
    """The sequence from the sixth finding, plus reservation interference."""
    assert_parity(
        stores,
        [
            set_ref("alpha", "ref-1"),
            edit("alpha", "superseding text"),
            track_cleanup("alpha", "ref-1"),
            set_ref("alpha", "ref-1"),
            set_ref("alpha", "ref-2"),
            resolve_cleanup("alpha", "ref-1"),
        ],
    )


def test_two_records_do_not_leak_freshness_into_each_other(stores) -> None:  # noqa: ANN001
    """Freshness is per record, and an edit to one must not free the other."""
    assert_parity(
        stores,
        [
            set_ref("alpha", "ref-1"),
            set_ref("beta", "ref-2"),
            edit("alpha", "superseding text"),
            set_ref("beta", "ref-3"),
            edit("beta", "superseding text too"),
            set_ref("alpha", "ref-4"),
        ],
    )


# A small alphabet is enough: every historical bug was reachable in six steps.
_ALPHABET = [
    set_ref("alpha", "ref-1"),
    set_ref("alpha", "ref-2"),
    set_ref("beta", "ref-1"),
    set_ref("beta", "ref-2"),
    edit("alpha", "superseding alpha"),
    edit("beta", "superseding beta"),
    track_cleanup("alpha", "ref-1"),
    track_cleanup("beta", "ref-2"),
    resolve_cleanup("alpha", "ref-1"),
]


def _sequences(seed: int, length: int, count: int) -> Iterator[list[Any]]:
    """Deterministic pseudo-random sequences; no clock, no global random."""

    state = seed
    for _ in range(count):
        sequence = []
        for _ in range(length):
            state = (state * 1103515245 + 12345) % (2**31)
            sequence.append(_ALPHABET[state % len(_ALPHABET)])
        yield sequence


@pytest.mark.parametrize("seed", range(10))
def test_generated_sequences_keep_the_stores_in_agreement(stores, seed: int) -> None:  # noqa: ANN001
    """Catches divergence in orderings nobody thought to write down.

    Deterministic by seed, so a failure names the exact sequence to replay.
    """
    for sequence in _sequences(seed, length=6, count=1):
        assert_parity(stores, sequence)
