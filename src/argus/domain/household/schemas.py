"""Stored household records and wire schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Permission = Literal["view", "edit"]
HouseholdStatus = Literal["active", "closed"]
MemberRole = Literal["admin", "member"]


class CreateHouseholdRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=80)


class AcceptInvitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=8, max_length=200)


class TransferAdminRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=80)


class CreateAccountGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=80)
    permission: Permission = "view"


class UpdateAccountGrantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission: Permission


class MemberRecord(BaseModel):
    user_id: str
    role: MemberRole
    joined_at: datetime


class HouseholdRecord(BaseModel):
    id: str
    name: str | None
    status: HouseholdStatus
    admin_user_id: str
    created_by: str
    created_at: datetime
    closed_at: datetime | None
    members: list[MemberRecord]


class InvitationCreated(BaseModel):
    id: str
    household_id: str
    expires_at: datetime
    token: str


class AccountGrantRecord(BaseModel):
    id: str
    household_id: str
    account_id: str
    owner_user_id: str
    permission: Permission
    created_at: datetime
    revoked_at: datetime | None = None


class SharedAccountView(BaseModel):
    grant_id: str
    account_id: str
    owner_user_id: str
    permission: Permission
    type: str
    currency: str
    nickname: str | None
    archived: bool
    ownership_share_bps: int


class OwnedAccountRef(BaseModel):
    """Minimal account facts needed to validate and project a grant."""

    id: str
    user_id: str
    type: str
    currency: str
    nickname: str | None
    archived: bool
    ownership_share_bps: int
