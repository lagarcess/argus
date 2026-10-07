"""WhatsApp settings, read from ``ARGUS_WHATSAPP_*``.

Intake is off unless ``ARGUS_WHATSAPP_INTAKE_ENABLED`` is a true value and every
credential it needs is present. Outbound replies are a second switch,
``ARGUS_WHATSAPP_OUTBOUND_ENABLED``, so intake can be proven without sending.
"""

from __future__ import annotations

from typing import Annotated

from loguru import logger
from pydantic import BeforeValidator, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from argus.api.financial_accounts import TRUE_VALUES


def _flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return value is not None and str(value).strip().lower() in TRUE_VALUES


def _blank_to_none(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        return None
    return value.strip() if isinstance(value, str) else value


Flag = Annotated[bool, BeforeValidator(_flag)]
Optional = Annotated[str | None, BeforeValidator(_blank_to_none)]
Secret = Annotated[SecretStr | None, BeforeValidator(_blank_to_none)]


class WhatsAppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARGUS_WHATSAPP_", extra="ignore")

    intake_enabled: Flag = False
    outbound_enabled: Flag = False
    verify_token: Secret = None
    app_secret: Secret = None
    access_token: Secret = None
    sender_key: Secret = None
    phone_number_id: Optional = None
    display_phone_number: Optional = None
    graph_api_version: str = "v23.0"

    @property
    def intake_ready(self) -> bool:
        return self.intake_enabled and None not in (
            self.verify_token,
            self.app_secret,
            self.access_token,
            self.sender_key,
            self.phone_number_id,
        )

    @property
    def wa_me_number(self) -> str | None:
        digits = "".join(ch for ch in self.display_phone_number or "" if ch.isdigit())
        return digits or None


def _version_ok(version: str) -> bool:
    major, dot, minor = version.removeprefix("v").partition(".")
    return version.startswith("v") and major.isdigit() and (not dot or minor.isdigit())


_warned: set[str] = set()


def _warn_once(message: str) -> None:
    if message not in _warned:
        _warned.add(message)
        logger.warning(message)


def load_whatsapp_settings() -> WhatsAppSettings:
    """Current settings, or an all-off snapshot when they cannot be read."""

    try:
        settings = WhatsAppSettings()
    except ValidationError:
        _warn_once("WhatsApp settings are invalid; intake stays off")
        return WhatsAppSettings.model_construct(intake_enabled=False)
    if not _version_ok(settings.graph_api_version):
        _warn_once("WhatsApp Graph API version is malformed; intake stays off")
        return WhatsAppSettings.model_construct(intake_enabled=False)
    if settings.intake_enabled and not settings.intake_ready:
        _warn_once("WhatsApp intake is enabled without its credentials; it stays off")
    return settings
