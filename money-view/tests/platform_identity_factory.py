"""Real durable identities for isolated domain tests; no authorization bypasses."""

from server.platform.common import active_context, now
from server.platform.identity import DEMO_PASSWORD, Identity
from server.store import Store


def identity_context(
    store: Store,
    *,
    user_id: str = "user-demo",
    household_id: str = "household-demo",
    role: str = "owner",
):
    identity = Identity(store)
    identity.initialize()
    with store.connection(write=True) as connection:
        stamp = now().isoformat()
        connection.execute(
            "INSERT OR IGNORE INTO p_households(id,name,country,currency_override,created_at) "
            "SELECT ?,?,country,currency_override,? FROM p_households WHERE id='household-demo'",
            (household_id, household_id, stamp),
        )
        if not connection.execute(
            "SELECT 1 FROM p_users WHERE id=?", (user_id,)
        ).fetchone():
            identity._create_user(connection, user_id, user_id, DEMO_PASSWORD, stamp)
        connection.execute(
            "INSERT OR IGNORE INTO p_memberships(household_id,user_id,role) VALUES(?,?,?)",
            (household_id, user_id, role),
        )
        result = active_context(
            connection,
            user_id=user_id,
            household_id=household_id,
            session_id=f"domain-test-{user_id}",
        )
        assert result.role == role, "Fixture must not silently alter existing authority"
        return result
