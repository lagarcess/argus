"""Business pilot settings.

``ARGUS_BUSINESS_PILOT_ENABLED`` uses the same true-value set as the other
default-off surfaces. Anything else, including a blank or unrecognized value,
leaves the surface off, and settings that cannot be read leave it off too.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from argus.domain.ingestion.documents.config import enabled_flag


class BusinessPilotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARGUS_BUSINESS_PILOT_", extra="ignore")
    enabled: Annotated[bool, BeforeValidator(enabled_flag)] = False


def business_pilot_enabled() -> bool:
    try:
        return BusinessPilotSettings().enabled
    except ValidationError:
        return False


class BusinessChatSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARGUS_BUSINESS_CHAT_", extra="ignore")
    enabled: Annotated[bool, BeforeValidator(enabled_flag)] = False


def business_chat_enabled() -> bool:
    """Nested inside the pilot. Off until Business turns have their own tool
    restrictions; reading and deleting Business chats never depends on it."""

    if not business_pilot_enabled():
        return False
    try:
        return BusinessChatSettings().enabled
    except ValidationError:
        return False
