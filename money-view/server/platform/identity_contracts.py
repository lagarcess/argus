"""Validated local identity commands and the single preference policy."""

from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BeforeValidator, Field, field_validator

from .common import CURRENCY_DIGITS, Model

Role = Literal["owner", "editor", "viewer"]
AvatarColor = Literal["forest", "ocean", "clay", "gold", "plum"]
Password = Annotated[str, Field(min_length=10, max_length=128)]
Name = Annotated[
    str,
    BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
    Field(min_length=1, max_length=80),
]
PreferredName = Annotated[
    Annotated[str, Field(max_length=40)] | None,
    BeforeValidator(lambda v: (v.strip() or None) if isinstance(v, str) else v),
]
COUNTRY_CURRENCY = {
    "DO": "DOP",
    "US": "USD",
    "NZ": "NZD",
    "ES": "EUR",
    "GB": "GBP",
    "CA": "CAD",
    "JP": "JPY",
    "KW": "KWD",
}


class Preferences(Model):
    locale: Literal["en", "es-419"] = "es-419"
    timezone: str = "America/Santo_Domingo"
    appearance: Literal["light", "dark", "system"] = "light"
    sidebar_compact: bool = False
    notifications: dict[str, bool] = Field(
        default_factory=lambda: {
            "bills": True,
            "account_changes": True,
            "product_updates": False,
        }
    )


class NotificationPatch(Model):
    bills: bool | None = None
    account_changes: bool | None = None
    product_updates: bool | None = None


class PreferencePatch(Model):
    locale: Literal["en", "es-419"] | None = None
    timezone: str | None = Field(default=None, max_length=100)
    appearance: Literal["light", "dark", "system"] | None = None
    sidebar_compact: bool | None = None
    notifications: NotificationPatch | None = None

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value):
        if value is not None:
            try:
                ZoneInfo(value)
            except (ZoneInfoNotFoundError, ValueError) as exc:
                raise ValueError("unknown_timezone") from exc
        return value


class ProfilePatch(Model):
    display_name: Name | None = None
    preferred_name: PreferredName = None
    avatar_color: AvatarColor | None = None


class HouseholdPatch(Model):
    name: Name | None = None
    country: str | None = None
    currency_override: str | None = None

    @field_validator("country")
    @classmethod
    def known_country(cls, value):
        if value is not None and value not in COUNTRY_CURRENCY:
            raise ValueError("unsupported_country")
        return value

    @field_validator("currency_override")
    @classmethod
    def known_currency(cls, value):
        if value is not None and value not in CURRENCY_DIGITS:
            raise ValueError("unsupported_currency")
        return value


class Login(Model):
    user_id: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)
    household_id: str | None = Field(default=None, max_length=100)


class HouseholdSwitch(Model):
    household_id: str = Field(min_length=1, max_length=100)


class LocalMember(Model):
    display_name: Name
    password: Password
    role: Role = "viewer"


class MemberRole(Model):
    role: Role


class SessionRevoke(Model):
    scope: Literal["others", "all"]


class PasswordChange(Model):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: Password


class MemoryWrite(Model):
    content: Annotated[
        str,
        BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
        Field(min_length=1, max_length=2000),
    ]
    confirmed: Literal[True]


class MemoryToggle(Model):
    enabled: bool


class Confirmation(Model):
    confirmation: str = Field(max_length=100)


class AccountDelete(Confirmation):
    current_password: str = Field(min_length=1, max_length=128)


class FeedbackWrite(Model):
    kind: Literal["bug", "feature", "general"]
    message: Annotated[
        str,
        BeforeValidator(lambda v: v.strip() if isinstance(v, str) else v),
        Field(min_length=1, max_length=4000),
    ]
