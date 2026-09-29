"""One reviewed command for personal money movements."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ActivityKind = Literal["expense", "income", "transfer", "card_payment", "refund"]
SOURCE_IDS = ("salary", "remittance", "interest", "other")
LIQUID_TYPES = ("cash", "checking", "savings", "investment")
ELIGIBILITY = {
    "expense": ("cash", "checking", "savings", "credit_card"),
    "income": LIQUID_TYPES,
    "refund": ("cash", "checking", "savings", "credit_card"),
    "transfer": LIQUID_TYPES,
    "card_payment": LIQUID_TYPES,
}


class MoneyCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: str
    observation_id: str
    included: bool

    @field_validator("account_id", "observation_id")
    @classmethod
    def uuid_value(cls, value: str) -> str:
        return str(UUID(value))


class MoneyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: ActivityKind
    account_id: str | None = None
    source_account_id: str | None = None
    destination_account_id: str | None = None
    amount: str = Field(max_length=40)
    occurred_at: datetime
    time_zone: str = Field(default="America/Santo_Domingo", max_length=64)
    note: str | None = Field(default=None, max_length=200)
    category_id: str | None = None
    source_id: str | None = None
    purchase_activity_id: str | None = None
    expected_revision: int | None = Field(default=None, ge=1)
    reason: str | None = Field(default=None, max_length=200)
    expected_versions: dict[str, int] = Field(default_factory=dict)
    coverage: list[MoneyCoverage] = Field(default_factory=list, max_length=1000)
    preview_token: str | None = Field(default=None, max_length=128)

    @field_validator(
        "account_id",
        "source_account_id",
        "destination_account_id",
        "purchase_activity_id",
    )
    @classmethod
    def uuid_value(cls, value: str | None) -> str | None:
        return str(UUID(value)) if value is not None else None

    @field_validator("expected_versions")
    @classmethod
    def versions(cls, value: dict[str, int]) -> dict[str, int]:
        if any(v < 1 for v in value.values()):
            raise ValueError("Account versions must be positive.")
        return {str(UUID(k)): v for k, v in value.items()}
