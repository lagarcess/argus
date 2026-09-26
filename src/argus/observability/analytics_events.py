"""The closed product analytics registry: Iris's wave 1 events, and nothing else.

Each event is one Pydantic model whose fields are the event's exact properties.
Fields are typed only as ``Literal[...]``, ``bool``, a bounded ``int``, or the
one pattern-constrained ``cohort`` string, so an amount, a name, an email, or
any other free text cannot be represented, let alone sent (SPEC 0, 0.5, A4).

PostHog receives each event under its own name. The sink in ``envelope.py``
refuses every envelope that did not come through ``capture_analytics_event()``,
so this module is the only way an event reaches PostHog.
"""

from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from argus.observability.envelope import (
    ArgusEventEnvelope,
    EventCaptureResult,
    capture_event,
)
from argus.observability.product_events import actor_hash_for_user

ANALYTICS_SCHEMA_VERSION = "argus_analytics_event/v1"

# The invite cohort code (SPEC 0, 0C-9). The only non-literal string an event
# may carry. The request field, the database check, and the browser guard must
# agree with this pattern; 0C-9 reuses this type rather than restating it.
INVITE_COHORT_PATTERN = r"^[a-z]{2,12}-[a-z0-9]{4,8}$"
InviteCohort = Annotated[
    str,
    StringConstraints(pattern=INVITE_COHORT_PATTERN, max_length=21),
]

# The registered calculations (``get_calculation_declarations()``). A test
# holds this list equal to the catalog, so a new calculation fails CI here
# until it is added.
CalculationName = Literal[
    "time_value",
    "growth_projection",
    "bond_value",
    "discounted_cash_flow",
    "price_multiple",
    "income_yield",
    "effective_rate",
    "debt_to_income",
    "expense_ratio",
    "ranked_comparison",
    "valuation_scenarios",
]
AnalyticsLanguage = Literal["en", "es-419"]

# No real person has been using Argus for a century.
MAX_DAYS_SINCE_SIGNUP = 36_500


class AnalyticsEvent(BaseModel):
    """One analytics event. Subclasses set ``event_name`` and their properties."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_name: ClassVar[str]
    # Only ``signed_in`` links an account to the guest it came from (C3).
    carries_guest_id_hash: ClassVar[bool] = False

    @model_validator(mode="before")
    @classmethod
    def _reject_lookalike_numbers(cls, data: Any) -> Any:
        # ``True == 1 == 1.0``, so a literal like ``step: 1`` would otherwise
        # accept a bool or a float. No property is a float, and only a
        # ``bool`` field takes a bool.
        if isinstance(data, dict):
            for name, value in data.items():
                field = cls.model_fields.get(name)
                if field is None or field.annotation is bool:
                    continue
                if isinstance(value, bool | float):
                    raise ValueError(f"{name} does not take a {type(value).__name__}")
        return data


class FirstAnswerShown(AnalyticsEvent):
    event_name: ClassVar[str] = "first_answer_shown"

    account_kind: Literal["guest", "signed_in"]
    chip_audience: Literal["everyday", "practitioner", "none"]
    language: AnalyticsLanguage
    cohort: InviteCohort | None = None


class SignedIn(AnalyticsEvent):
    event_name: ClassVar[str] = "signed_in"
    carries_guest_id_hash: ClassVar[bool] = True

    signup: Literal["new", "returning"]
    trigger: Literal["save", "goal", "checklist", "other"]
    cohort: InviteCohort | None = None


class CardSaved(AnalyticsEvent):
    event_name: ClassVar[str] = "card_saved"

    calculator: CalculationName | Literal["backtest"]


class GoalCreated(AnalyticsEvent):
    event_name: ClassVar[str] = "goal_created"

    goal_type: Literal["savings"]


class ChecklistStepCompleted(AnalyticsEvent):
    event_name: ClassVar[str] = "checklist_step_completed"

    step: Literal[1, 2, 3]


class RemindersOptedIn(AnalyticsEvent):
    event_name: ClassVar[str] = "reminders_opted_in"

    channel: Literal["email", "push"]


class RemindersOptedOut(AnalyticsEvent):
    event_name: ClassVar[str] = "reminders_opted_out"

    channel: Literal["email", "push"]


class SessionStarted(AnalyticsEvent):
    event_name: ClassVar[str] = "session_started"

    days_since_signup: Annotated[int, Field(ge=0, le=MAX_DAYS_SINCE_SIGNUP)]
    cohort: InviteCohort | None = None


class InstalledAppOpened(AnalyticsEvent):
    event_name: ClassVar[str] = "installed_app_opened"


class LandingViewed(AnalyticsEvent):
    event_name: ClassVar[str] = "landing_viewed"

    language: AnalyticsLanguage
    cohort: InviteCohort | None = None


class ReceiptShared(AnalyticsEvent):
    event_name: ClassVar[str] = "receipt_shared"

    calculator: CalculationName | Literal["backtest", "multiple", "none"]


ANALYTICS_EVENT_MODELS: dict[str, type[AnalyticsEvent]] = {
    model.event_name: model
    for model in (
        FirstAnswerShown,
        SignedIn,
        CardSaved,
        GoalCreated,
        ChecklistStepCompleted,
        RemindersOptedIn,
        RemindersOptedOut,
        SessionStarted,
        InstalledAppOpened,
        LandingViewed,
        ReceiptShared,
    )
}

# Sent with every event besides the model's own fields (SPEC 0, 0.5).
TECHNICAL_PROPERTIES: frozenset[str] = frozenset(
    {
        "$process_person_profile",
        "environment",
        "internal_account",
        "schema_version",
        "event_id",
    }
)


def build_analytics_envelope(
    event: AnalyticsEvent,
    *,
    user_id: str,
    guest_user_id: str | None = None,
    internal_account: bool,
) -> ArgusEventEnvelope:
    if ANALYTICS_EVENT_MODELS.get(event.event_name) is not type(event):
        raise TypeError(f"{type(event).__name__} is not a registered analytics event")
    actor_hash = actor_hash_for_user(user_id)
    if actor_hash is None:
        raise ValueError("an analytics event needs the user id it is about")
    properties = event.model_dump(mode="json", exclude_none=True)
    if guest_user_id is not None:
        if not event.carries_guest_id_hash:
            raise ValueError(f"{event.event_name} does not carry a guest id hash")
        guest_id_hash = actor_hash_for_user(guest_user_id)
        if guest_id_hash is not None:
            properties["guest_id_hash"] = guest_id_hash
    return ArgusEventEnvelope(
        schema_version=ANALYTICS_SCHEMA_VERSION,
        event_type="analytics",
        event_action="completed",
        feature_area="product_analytics",
        analytics_event=event.event_name,
        internal_account=internal_account,
        actor_hash=actor_hash,
        attributes=properties,
    )


def capture_analytics_event(
    event: AnalyticsEvent,
    *,
    user_id: str,
    guest_user_id: str | None = None,
    internal_account: bool,
) -> EventCaptureResult:
    """Send one registered event to PostHog under its own name.

    ``user_id`` is the account id for signed-in users and the guest user id for
    guests; PostHog sees only its hash. ``guest_user_id`` is accepted only on
    ``signed_in`` and becomes ``guest_id_hash``, the same hash the guest's own
    events used as their ``distinct_id``.
    """
    return capture_event(
        build_analytics_envelope(
            event,
            user_id=user_id,
            guest_user_id=guest_user_id,
            internal_account=internal_account,
        )
    )
