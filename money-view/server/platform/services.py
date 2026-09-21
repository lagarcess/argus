"""Local service catalogs and durable, household-scoped demo workflows."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from fastapi.responses import Response

from .common import PlatformError, assert_active_context, identifier, now, require_editor
from .credit import router as credit_router
from .service_contracts import (
    TABLES,
    Benefit,
    ContextDependency,
    Enrollment,
    Membership,
    Reschedule,
    Reservation,
    StoreDependency,
    evidence,
    record,
    rows,
    save,
)
from .tax_estate import router as tax_estate_router

router = APIRouter(prefix="/api/platform")
router.include_router(credit_router)
router.include_router(tax_estate_router)

SPECIALISTS = [
    {
        "id": "specialist-budget",
        "name": "Alex Morgan (demo)",
        "specialty": "budgeting",
        "demo": True,
    },
    {
        "id": "specialist-organizer",
        "name": "Jordan Lee (demo)",
        "specialty": "document_organization",
        "demo": True,
    },
]
BENEFITS = [
    {"id": "learning", "title": "financial_learning"},
    {"id": "wellness", "title": "wellness_resources"},
    {"id": "planning", "title": "planning_workshop"},
]
PLAN_VALUES = {"monthly": ("9", "month"), "annual": ("90", "year")}


def plans():
    return [
        {
            "id": key,
            "amount": amount,
            "currency": "USD",
            "interval": interval,
            "evidence": {
                **evidence(f"plan-{key}", "2026-09-20", "synthetic"),
                "recorded_at": "2026-09-20T00:00:00+00:00",
            },
        }
        for key, (amount, interval) in PLAN_VALUES.items()
    ]


def ensure_future_slots(db):
    """Keep six future demo days; retain every slot referenced by a reservation."""
    current = now().astimezone(timezone.utc)
    first_day = (current + timedelta(days=1)).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    for day_offset in range(6):
        for specialist_index, specialist in enumerate(SPECIALISTS):
            start = first_day + timedelta(days=day_offset, hours=specialist_index)
            # Existing fixtures may use older IDs. The catalog owns the time, too.
            if db.execute(
                "SELECT 1 FROM p_service_slots WHERE specialist_id=? AND starts_at=?",
                (specialist["id"], start.isoformat()),
            ).fetchone():
                continue
            db.execute(
                "INSERT OR IGNORE INTO p_service_slots VALUES(?,?,?,?)",
                (
                    f"slot-demo-{start.strftime('%Y%m%dT%H%M')}",
                    specialist["id"],
                    start.isoformat(),
                    (start + timedelta(minutes=45)).isoformat(),
                ),
            )
    db.execute(
        """DELETE FROM p_service_slots WHERE starts_at<=? AND NOT EXISTS(
        SELECT 1 FROM p_service_reservations r WHERE r.slot_id=p_service_slots.id OR r.original_slot_id=p_service_slots.id)""",
        (current.isoformat(),),
    )


def initialize(store):
    with store.connection(write=True) as db:
        for table in TABLES:
            db.execute(
                f"CREATE TABLE IF NOT EXISTS {table}(id TEXT NOT NULL,household_id TEXT NOT NULL,document TEXT NOT NULL,PRIMARY KEY(household_id,id))"
            )
        db.execute("CREATE TABLE IF NOT EXISTS p_service_manifest(id TEXT PRIMARY KEY)")
        db.execute(
            "CREATE TABLE IF NOT EXISTS p_service_slots(id TEXT PRIMARY KEY,specialist_id TEXT NOT NULL,starts_at TEXT NOT NULL,ends_at TEXT NOT NULL)"
        )
        db.execute("""CREATE TABLE IF NOT EXISTS p_service_reservations(
            id TEXT PRIMARY KEY, household_id TEXT NOT NULL, slot_id TEXT NOT NULL REFERENCES p_service_slots(id),
            original_slot_id TEXT NOT NULL, request_key TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('reserved','cancelled')),
            recorded_at TEXT NOT NULL, UNIQUE(household_id,request_key))""")
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS p_service_reserved_slot ON p_service_reservations(slot_id) WHERE status='reserved'"
        )
        ensure_future_slots(db)
        if db.execute(
            "SELECT 1 FROM p_service_manifest WHERE id='services-v1'"
        ).fetchone():
            return
        db.execute("INSERT INTO p_service_manifest(id) VALUES('services-v1')")
        household = "household-demo"
        source = evidence("credit-demo", "2026-09-18", "synthetic")
        save(
            db,
            "p_credit_accounts",
            household,
            {
                "id": "credit-demo",
                "name": "Everyday card (demo)",
                "currency": "USD",
                "balance": "1240.50",
                "credit_limit": "6000.00",
                "apr_pct": "19.99",
                "minimum_payment": "60.00",
                "as_of": "2026-09-18",
                "evidence": source,
            },
        )
        save(
            db,
            "p_credit_reports",
            household,
            {
                "id": "report-demo",
                "score": 724,
                "scale_min": 300,
                "scale_max": 850,
                "history": [
                    {"as_of": "2026-06-18", "score": 710},
                    {"as_of": "2026-07-18", "score": 716},
                    {"as_of": "2026-08-18", "score": 720},
                    {"as_of": "2026-09-18", "score": 724},
                ],
                "factors": [
                    {"code": "payment_history", "impact": "positive"},
                    {"code": "credit_utilization", "impact": "mixed"},
                ],
                "evidence": evidence("report-demo", "2026-09-18", "synthetic"),
            },
        )
        recorded = now().isoformat()
        save(
            db,
            "p_tax_organizers",
            household,
            {
                "id": "tax-demo",
                "country": "DO",
                "year": 2026,
                "currency": "DOP",
                "status": "open",
                "recorded_at": recorded,
                "evidence": evidence("tax-demo", "2026-09-18", "synthetic"),
            },
        )
        for item_id, kind, title, amount in [
            ("income-demo", "income", "Independent project (demo)", "25000.00"),
            ("expense-demo", "expense", "Work supplies (demo)", "2500.00"),
            ("document-demo", "document", "Collect income statements", None),
        ]:
            save(
                db,
                "p_tax_items",
                household,
                {
                    "id": item_id,
                    "organizer_id": "tax-demo",
                    "kind": kind,
                    "title": title,
                    "amount": amount,
                    "effective_on": "2026-09-18",
                    "completed": False,
                    "recorded_at": recorded,
                    "evidence": evidence(item_id, "2026-09-18", "synthetic"),
                },
            )
        save(
            db,
            "p_estate_assets",
            household,
            {
                "id": "asset-demo",
                "name": "Savings account (demo)",
                "currency": "USD",
                "value": "4200.00",
                "as_of": "2026-09-18",
                "recorded_at": recorded,
                "evidence": evidence("asset-demo", "2026-09-18", "synthetic"),
            },
        )
        save(
            db,
            "p_estate_contacts",
            household,
            {
                "id": "contact-demo",
                "name": "Taylor Rivera (demo)",
                "relationship": "Sibling",
                "email": "taylor@example.test",
                "recorded_at": recorded,
            },
        )
        save(
            db,
            "p_estate_checklist",
            household,
            {
                "id": "checklist-demo",
                "title": "Review account inventory",
                "completed": False,
                "recorded_at": recorded,
            },
        )


def reservation_record(db, household, reservation_id):
    value = db.execute(
        "SELECT * FROM p_service_reservations WHERE household_id=? AND id=?",
        (household, reservation_id),
    ).fetchone()
    if value is None:
        raise PlatformError("record_not_found", 404)
    return dict(value)


def available_slot(db, slot_id, reservation_id=None):
    slot = db.execute("SELECT * FROM p_service_slots WHERE id=?", (slot_id,)).fetchone()
    if slot is None:
        raise PlatformError("slot_not_found", 404)
    if datetime.fromisoformat(slot["starts_at"]) <= now():
        raise PlatformError("slot_expired", 409)
    other = db.execute(
        "SELECT id FROM p_service_reservations WHERE slot_id=? AND status='reserved'",
        (slot_id,),
    ).fetchone()
    if other and other["id"] != reservation_id:
        raise PlatformError("slot_unavailable", 409)
    return slot


@router.get("/appointments")
def appointments(*, store: StoreDependency, context: ContextDependency):
    with store.connection(write=True) as db:
        assert_active_context(db, context, minimum_role="viewer")
        ensure_future_slots(db)
        slots = [
            dict(row)
            for row in db.execute(
                "SELECT s.*, NOT EXISTS(SELECT 1 FROM p_service_reservations r WHERE r.slot_id=s.id AND r.status='reserved') AS available FROM p_service_slots s ORDER BY starts_at"
            )
        ]
        for slot in slots:
            slot["available"] = (
                bool(slot["available"])
                and datetime.fromisoformat(slot["starts_at"]) > now()
            )
        reservations = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM p_service_reservations WHERE household_id=? ORDER BY recorded_at",
                (context.household_id,),
            )
        ]
    return {
        "specialists": SPECIALISTS,
        "slots": slots,
        "reservations": reservations,
        "mode": "local_demo",
    }


@router.post("/appointments")
def reserve(payload: Reservation, *, store: StoreDependency, context: ContextDependency):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        previous = db.execute(
            "SELECT * FROM p_service_reservations WHERE household_id=? AND request_key=?",
            (context.household_id, payload.request_key),
        ).fetchone()
        if previous:
            if previous["original_slot_id"] != payload.slot_id:
                raise PlatformError("idempotency_conflict", 409)
            return dict(previous)
        available_slot(db, payload.slot_id)
        reservation_id = identifier("reservation")
        db.execute(
            "INSERT INTO p_service_reservations VALUES(?,?,?,?,?,?,?)",
            (
                reservation_id,
                context.household_id,
                payload.slot_id,
                payload.slot_id,
                payload.request_key,
                "reserved",
                now().isoformat(),
            ),
        )
        return reservation_record(db, context.household_id, reservation_id)


@router.patch("/appointments/{reservation_id}")
def reschedule(
    reservation_id: str,
    payload: Reschedule,
    *,
    store: StoreDependency,
    context: ContextDependency,
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        current = reservation_record(db, context.household_id, reservation_id)
        if current["status"] != "reserved":
            raise PlatformError("reservation_cancelled", 409)
        available_slot(db, payload.slot_id, reservation_id)
        db.execute(
            "UPDATE p_service_reservations SET slot_id=? WHERE household_id=? AND id=?",
            (payload.slot_id, context.household_id, reservation_id),
        )
        return reservation_record(db, context.household_id, reservation_id)


@router.post("/appointments/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: str, *, store: StoreDependency, context: ContextDependency
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        reservation_record(db, context.household_id, reservation_id)
        db.execute(
            "UPDATE p_service_reservations SET status='cancelled' WHERE household_id=? AND id=?",
            (context.household_id, reservation_id),
        )
        return reservation_record(db, context.household_id, reservation_id)


@router.get("/appointments/{reservation_id}/calendar")
def calendar(reservation_id: str, *, store: StoreDependency, context: ContextDependency):
    with store.connection() as db:
        item = reservation_record(db, context.household_id, reservation_id)
        slot = db.execute(
            "SELECT * FROM p_service_slots WHERE id=?", (item["slot_id"],)
        ).fetchone()

    def stamp(value):
        return (
            datetime.fromisoformat(value)
            .astimezone(timezone.utc)
            .strftime("%Y%m%dT%H%M%SZ")
        )

    content = "\r\n".join(
        [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Clara//Local Demo//EN",
            "BEGIN:VEVENT",
            f"UID:{item['id']}@clara.local",
            f"DTSTAMP:{stamp(item['recorded_at'])}",
            f"DTSTART:{stamp(slot['starts_at'])}",
            f"DTEND:{stamp(slot['ends_at'])}",
            "SUMMARY:Clara local demo session",
            "DESCRIPTION:Local demonstration only. No real appointment or contact.",
            "STATUS:CANCELLED" if item["status"] == "cancelled" else "STATUS:TENTATIVE",
            "END:VEVENT",
            "END:VCALENDAR",
            "",
        ]
    )
    return Response(
        content,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="clara-demo.ics"'},
    )


@router.get("/membership")
def membership(*, store: StoreDependency, context: ContextDependency):
    with store.connection() as db:
        memberships = rows(db, "p_service_memberships", context.household_id)
        receipts = rows(db, "p_membership_receipts", context.household_id)
    return {
        "plans": plans(),
        "membership": memberships[0] if memberships else None,
        "receipts": receipts,
        "mode": "local_demo",
    }


def membership_from_receipt(receipt):
    return {
        "id": "membership",
        "plan_id": receipt["plan_id"],
        "status": "active",
        "recorded_at": receipt["recorded_at"],
    }


@router.post("/membership")
def subscribe(payload: Membership, *, store: StoreDependency, context: ContextDependency):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        for receipt in rows(db, "p_membership_receipts", context.household_id):
            if receipt["request_key"] == payload.request_key:
                if receipt["plan_id"] != payload.plan_id:
                    raise PlatformError("idempotency_conflict", 409)
                return {
                    "membership": membership_from_receipt(receipt),
                    "receipt": receipt,
                }
        amount, _ = PLAN_VALUES[payload.plan_id]
        receipt = {
            "id": identifier("receipt"),
            "plan_id": payload.plan_id,
            "request_key": payload.request_key,
            "amount": amount,
            "currency": "USD",
            "status": "simulated_no_charge",
            "recorded_at": now().isoformat(),
        }
        current = membership_from_receipt(receipt)
        save(db, "p_service_memberships", context.household_id, current)
        save(db, "p_membership_receipts", context.household_id, receipt)
        return {"membership": current, "receipt": receipt}


@router.post("/membership/cancel")
def cancel_membership(*, store: StoreDependency, context: ContextDependency):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        memberships = rows(db, "p_service_memberships", context.household_id)
        if not memberships:
            return {"membership": None}
        return {
            "membership": save(
                db,
                "p_service_memberships",
                context.household_id,
                {**memberships[0], "status": "cancelled"},
            )
        }


@router.get("/employer")
def employer(*, store: StoreDependency, context: ContextDependency):
    with store.connection() as db:
        enrollments = rows(db, "p_employer_enrollments", context.household_id)
    return {
        "enrollment": enrollments[0] if enrollments else None,
        "demo_code": "CLARA-DEMO",
        "benefits": BENEFITS,
        "mode": "local_demo",
    }


@router.post("/employer/enroll")
def enroll(payload: Enrollment, *, store: StoreDependency, context: ContextDependency):
    require_editor(context)
    if payload.code != "CLARA-DEMO":
        raise PlatformError("invalid_demo_employer_code")
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        previous = rows(db, "p_employer_enrollments", context.household_id)
        if previous and previous[0]["status"] == "enrolled":
            return previous[0]
        return save(
            db,
            "p_employer_enrollments",
            context.household_id,
            {
                "id": "enrollment",
                "employer_id": "employer-demo",
                "benefit_id": None,
                "status": "enrolled",
                "recorded_at": now().isoformat(),
            },
        )


@router.put("/employer/benefit")
def choose_benefit(
    payload: Benefit, *, store: StoreDependency, context: ContextDependency
):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        current = record(db, "p_employer_enrollments", context.household_id, "enrollment")
        if current["status"] != "enrolled":
            raise PlatformError("employer_not_enrolled", 409)
        return save(
            db,
            "p_employer_enrollments",
            context.household_id,
            {**current, "benefit_id": payload.benefit_id},
        )


@router.post("/employer/leave")
def leave_employer(*, store: StoreDependency, context: ContextDependency):
    require_editor(context)
    with store.connection(write=True) as db:
        assert_active_context(db, context)
        previous = rows(db, "p_employer_enrollments", context.household_id)
        if not previous:
            return {"enrollment": None}
        return {
            "enrollment": save(
                db,
                "p_employer_enrollments",
                context.household_id,
                {**previous[0], "status": "left", "benefit_id": None},
            )
        }


def export_data(connection, ctx):
    result = {table: rows(connection, table, ctx.household_id) for table in TABLES}
    result["p_service_reservations"] = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM p_service_reservations WHERE household_id=?",
            (ctx.household_id,),
        )
    ]
    return result


def clear_data(connection, ctx):
    for table in (*TABLES, "p_service_reservations"):
        connection.execute(
            f"DELETE FROM {table} WHERE household_id=?", (ctx.household_id,)
        )


def usage_data(connection, ctx):
    return {
        "service_records": sum(
            connection.execute(
                f"SELECT count(*) FROM {table} WHERE household_id=?", (ctx.household_id,)
            ).fetchone()[0]
            for table in (*TABLES, "p_service_reservations")
        )
    }
