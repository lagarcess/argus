"""Personal settings and explicitly scoped local data lifecycle."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse

from .common import (
    Context,
    PlatformError,
    assert_active_context,
    get_context,
    identifier,
    now,
    require_owner,
)
from .identity import (
    COOKIE,
    ExportReader,
    Identity,
    delete_local_identity,
    get_identity,
    household,
    password_matches,
    profile,
)
from .identity_contracts import (
    AccountDelete,
    Confirmation,
    FeedbackWrite,
    MemoryToggle,
    MemoryWrite,
    PreferencePatch,
    Preferences,
    ProfilePatch,
)
from .identity_lifecycle import advance_household_generation

router = APIRouter()


def memory_data(db, context: Context) -> dict:
    enabled = db.execute(
        "SELECT enabled FROM p_memory_settings WHERE user_id=? AND household_id=?",
        (context.user_id, context.household_id),
    ).fetchone()
    items = [
        dict(row)
        for row in db.execute(
            "SELECT id,content,created_at,updated_at FROM p_memories WHERE user_id=? AND household_id=? ORDER BY created_at,id",
            (context.user_id, context.household_id),
        )
    ]
    return {"enabled": bool(enabled and enabled[0]), "items": items, "local_only": True}


def require_confirmation(command: Confirmation, expected: str) -> None:
    if command.confirmation != expected:
        raise PlatformError("confirmation_required")


def json_download(document: dict, filename: str) -> JSONResponse:
    return JSONResponse(
        document,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


def feedback_data(db, context: Context) -> list[dict]:
    return [
        {**dict(row), "status": "saved_locally", "local_only": True}
        for row in db.execute(
            "SELECT id,kind,message,created_at FROM p_local_feedback WHERE user_id=? AND household_id=? ORDER BY created_at DESC,id",
            (context.user_id, context.household_id),
        )
    ]


@router.get("/settings")
def settings(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    snapshot = identity.snapshot(context)
    with identity.store.connection() as db:
        memories = memory_data(db, context)
    return {
        "profile": snapshot["user"],
        "preferences": snapshot["preferences"],
        "household": snapshot["household"],
        "supported_currencies": snapshot["supported_currencies"],
        "memory": {"enabled": memories["enabled"], "count": len(memories["items"])},
        "capabilities": {
            "local_passwords": True,
            "confirmed_memories": True,
            "data_domains": list(identity.data_domains),
            "archive_conversations": "assistant" in identity.data_domains,
            "public_sharing": False,
            "outbound_support": False,
            "notification_delivery": "in_app_only",
        },
    }


@router.patch("/settings/profile")
def patch_profile(
    command: ProfilePatch,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    changes = command.model_dump(exclude_unset=True)
    if any(value is None for key, value in changes.items() if key != "preferred_name"):
        raise PlatformError("invalid_profile")
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        for key, value in changes.items():
            db.execute(f"UPDATE p_users SET {key}=? WHERE id=?", (value, context.user_id))
        return profile(
            db.execute("SELECT * FROM p_users WHERE id=?", (context.user_id,)).fetchone()
        )


@router.patch("/settings/preferences")
def patch_preferences(
    command: PreferencePatch,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    changes = command.model_dump(exclude_unset=True, exclude_none=True)
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        document = json.loads(
            db.execute(
                "SELECT document FROM p_preferences WHERE user_id=?", (context.user_id,)
            ).fetchone()[0]
        )
        for key, value in changes.items():
            if key == "notifications":
                document[key].update(value)
            else:
                document[key] = value
        validated = Preferences.model_validate(document)
        db.execute(
            "UPDATE p_preferences SET document=? WHERE user_id=?",
            (validated.model_dump_json(), context.user_id),
        )
    return validated


@router.get("/settings/memories")
def memories(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection() as db:
        return memory_data(db, context)


@router.patch("/settings/memories")
def toggle_memories(
    command: MemoryToggle,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        db.execute(
            "INSERT INTO p_memory_settings VALUES (?,?,?) ON CONFLICT(user_id,household_id) DO UPDATE SET enabled=excluded.enabled",
            (context.user_id, context.household_id, int(command.enabled)),
        )
        return memory_data(db, context)


@router.post("/settings/memories", status_code=201)
def create_memory(
    command: MemoryWrite,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    memory_id, timestamp = identifier("memory"), now().isoformat()
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        db.execute(
            "INSERT INTO p_memories VALUES (?,?,?,?,?,?)",
            (
                memory_id,
                context.user_id,
                context.household_id,
                command.content,
                timestamp,
                timestamp,
            ),
        )
    return {
        "id": memory_id,
        "content": command.content,
        "created_at": timestamp,
        "updated_at": timestamp,
    }


@router.patch("/settings/memories/{memory_id}")
def update_memory(
    memory_id: str,
    command: MemoryWrite,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        changed = db.execute(
            "UPDATE p_memories SET content=?,updated_at=? WHERE id=? AND user_id=? AND household_id=?",
            (
                command.content,
                now().isoformat(),
                memory_id,
                context.user_id,
                context.household_id,
            ),
        ).rowcount
        if not changed:
            raise PlatformError("memory_not_found", 404)
        return dict(
            db.execute(
                "SELECT id,content,created_at,updated_at FROM p_memories WHERE id=? AND user_id=? AND household_id=?",
                (memory_id, context.user_id, context.household_id),
            ).fetchone()
        )


@router.delete("/settings/memories/{memory_id}")
def delete_memory(
    memory_id: str,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        changed = db.execute(
            "DELETE FROM p_memories WHERE id=? AND user_id=? AND household_id=?",
            (memory_id, context.user_id, context.household_id),
        ).rowcount
        if not changed:
            raise PlatformError("memory_not_found", 404)
    return {"deleted": True}


@router.post("/settings/memories/reset")
def reset_memories(
    command: Confirmation,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    require_confirmation(command, "DELETE MY MEMORIES")
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        count = db.execute(
            "DELETE FROM p_memories WHERE user_id=? AND household_id=?",
            (context.user_id, context.household_id),
        ).rowcount
    return {"deleted": count}


@router.get("/settings/memories/export")
def export_memories(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection() as db:
        return json_download(memory_data(db, context), "clara-confirmed-memories.json")


@router.get("/settings/data/export")
def export_data(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection() as connection:
        db = ExportReader(connection)
        user = db.execute(
            "SELECT id,display_name,preferred_name,avatar_color FROM p_users WHERE id=?",
            (context.user_id,),
        ).fetchone()
        prefs = json.loads(
            db.execute(
                "SELECT document FROM p_preferences WHERE user_id=?", (context.user_id,)
            ).fetchone()[0]
        )
        home = household(
            db.execute(
                "SELECT * FROM p_households WHERE id=?", (context.household_id,)
            ).fetchone()
        )
        members = [
            dict(row)
            for row in db.execute(
                "SELECT u.id,u.display_name,m.role FROM p_users u JOIN p_memberships m ON m.user_id=u.id WHERE m.household_id=?",
                (context.household_id,),
            )
        ]
        document = {
            "schema_version": 1,
            "exported_at": now().isoformat(),
            "local_only": True,
            "household_id": context.household_id,
            "identity": {
                "profile": profile(user),
                "preferences": prefs,
                "household": home,
                "members": members,
                "memories": memory_data(db, context),
                "feedback": feedback_data(db, context),
            },
            "domains": {
                name: domain.export(db, context)
                for name, domain in identity.data_domains.items()
            },
        }
    return json_download(document, "clara-household-export.json")


@router.get("/settings/usage")
def usage(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    timestamp = now().isoformat()
    with identity.store.connection() as db:
        active = db.execute(
            "SELECT COUNT(*) FROM p_sessions WHERE user_id=? AND revoked_at IS NULL AND expires_at>?",
            (context.user_id, timestamp),
        ).fetchone()[0]
        memories = db.execute(
            "SELECT COUNT(*) FROM p_memories WHERE user_id=? AND household_id=?",
            (context.user_id, context.household_id),
        ).fetchone()[0]
        feedback = db.execute(
            "SELECT COUNT(*) FROM p_local_feedback WHERE user_id=? AND household_id=?",
            (context.user_id, context.household_id),
        ).fetchone()[0]
        domains = {
            name: domain.usage(db, context)
            for name, domain in identity.data_domains.items()
        }
    return {
        "as_of": timestamp,
        "local_only": True,
        "metrics": {
            "active_sessions": active,
            "confirmed_memories": memories,
            "local_feedback": feedback,
        },
        "domains": domains,
    }


def clear_identity_household(db, household_id: str) -> None:
    db.execute("DELETE FROM p_memories WHERE household_id=?", (household_id,))
    db.execute("DELETE FROM p_memory_settings WHERE household_id=?", (household_id,))
    db.execute("DELETE FROM p_local_feedback WHERE household_id=?", (household_id,))


@router.post("/settings/data/reset")
def reset_data(
    command: Confirmation,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    require_owner(context)
    require_confirmation(command, "RESET THIS HOUSEHOLD")
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="owner")
        for domain in identity.data_domains.values():
            domain.clear(db, context)
        clear_identity_household(db, context.household_id)
        advance_household_generation(db, context.household_id)
        db.execute(
            "UPDATE p_households SET country='DO',currency_override=NULL WHERE id=?",
            (context.household_id,),
        )
        db.execute(
            "UPDATE p_preferences SET document=? WHERE user_id=?",
            (Preferences().model_dump_json(), context.user_id),
        )
    return {
        "reset": True,
        "household_id": context.household_id,
        "domains": list(identity.data_domains),
        "requires_login": False,
    }


@router.delete("/settings/account")
def delete_account(
    command: AccountDelete,
    response: Response,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    require_confirmation(command, "DELETE MY LOCAL ACCOUNT")
    cleared = []
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        saved = db.execute(
            "SELECT password_hash FROM p_users WHERE id=?", (context.user_id,)
        ).fetchone()[0]
        if not password_matches(command.current_password, saved):
            raise PlatformError("invalid_credentials", 401)
        memberships = db.execute(
            "SELECT household_id,role FROM p_memberships WHERE user_id=?",
            (context.user_id,),
        ).fetchall()
        # Check all ownership constraints before any deletion or callback runs.
        private = []
        for member in memberships:
            counts = db.execute(
                "SELECT COUNT(*) AS members,SUM(role='owner') AS owners FROM p_memberships WHERE household_id=?",
                (member["household_id"],),
            ).fetchone()
            if (
                member["role"] == "owner"
                and counts["owners"] == 1
                and counts["members"] > 1
            ):
                raise PlatformError("last_owner_required", 409)
            if counts["members"] == 1:
                private.append(member["household_id"])
        for household_id in private:
            private_context = Context(
                context.user_id, household_id, "owner", context.session_id
            )
            for domain in identity.data_domains.values():
                domain.clear(db, private_context)
            clear_identity_household(db, household_id)
            advance_household_generation(db, household_id)
            db.execute(
                "UPDATE p_households SET name='Deleted local household',country='DO',currency_override=NULL WHERE id=?",
                (household_id,),
            )
            cleared.append(household_id)
        delete_local_identity(db, context.user_id)
    response.delete_cookie(COOKIE, path="/")
    return {
        "deleted": True,
        "logged_out": True,
        "shared_household_data_preserved": True,
        "private_households_cleared": cleared,
    }


@router.post("/settings/feedback", status_code=201)
def create_feedback(
    command: FeedbackWrite,
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    feedback_id, timestamp = identifier("feedback"), now().isoformat()
    with identity.store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        db.execute(
            "INSERT INTO p_local_feedback VALUES (?,?,?,?,?,?)",
            (
                feedback_id,
                context.user_id,
                context.household_id,
                command.kind,
                command.message,
                timestamp,
            ),
        )
    return {
        "id": feedback_id,
        "kind": command.kind,
        "message": command.message,
        "created_at": timestamp,
        "status": "saved_locally",
        "local_only": True,
    }


@router.get("/settings/feedback")
def feedback(
    context: Annotated[Context, Depends(get_context)],
    identity: Annotated[Identity, Depends(get_identity)],
):
    with identity.store.connection() as db:
        return {"items": feedback_data(db, context)}


@router.get("/settings/help")
def help_documents(context: Annotated[Context, Depends(get_context)]):
    return {
        "local_only": True,
        "documents": [
            {"id": key, "title_key": f"help.{key}.title", "body_key": f"help.{key}.body"}
            for key in ("guide", "privacy", "terms")
        ],
        "shortcuts": [{"keys": ["Escape"], "action_key": "help.shortcuts.close"}],
    }
