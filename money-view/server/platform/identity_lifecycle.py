"""Identity owns the monotonic household generation advanced by data clearing."""

from sqlite3 import Connection

SCHEMA = """
CREATE TABLE IF NOT EXISTS p_household_generations (
 household_id TEXT PRIMARY KEY REFERENCES p_households(id),
 generation INTEGER NOT NULL CHECK(generation >= 0)
);
"""


def advance_household_generation(connection: Connection, household_id: str) -> None:
    """Call in the same write transaction as the authorized household clear."""
    if not connection.in_transaction:
        raise RuntimeError("Generation advance requires an active write transaction")
    connection.execute(
        """INSERT INTO p_household_generations(household_id,generation) VALUES (?,1)
        ON CONFLICT(household_id) DO UPDATE SET generation=generation+1""",
        (household_id,),
    )
