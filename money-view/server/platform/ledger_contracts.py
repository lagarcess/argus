"""Validated ledger commands. Money signs describe net-worth changes."""
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import Amount, Model

Name = Annotated[str, Field(min_length=1, max_length=160)]
Key = Annotated[str, Field(min_length=1, max_length=120)]
Kind = Literal['expense', 'income', 'refund', 'transfer', 'adjustment']
AccountKind = Literal['checking', 'savings', 'credit_card', 'loan', 'investment', 'cash']
CATEGORIES = {
    'groceries': 'expense', 'dining': 'expense', 'housing': 'expense',
    'transport': 'expense', 'utilities': 'expense', 'health': 'expense',
    'shopping': 'expense', 'entertainment': 'expense', 'travel': 'expense',
    'education': 'expense', 'insurance': 'expense', 'other': 'expense',
    'income': 'income', 'transfer': 'transfer',
}


class Idempotent(Model):
    idempotency_key: Key


class AccountCreate(Idempotent):
    name: Name
    institution: Name = 'Manual'
    kind: AccountKind
    currency: str = Field(pattern=r'^[A-Z]{3}$')
    opening_balance: Amount = Decimal(0)


class AccountPatch(Model):
    name: Name | None = None
    institution: Name | None = None


class Split(Model):
    category: Name
    amount: Amount


class TransactionCreate(Idempotent):
    account_id: Name
    date: date
    merchant: Name
    description: str = Field(default='', max_length=500)
    amount: Amount
    category: Name
    kind: Kind = 'expense'
    status: Literal['posted', 'pending'] = 'posted'
    notes: str = Field(default='', max_length=1000)
    splits: list[Split] = Field(default_factory=list, max_length=20)
    to_account_id: Name | None = None

    @model_validator(mode='after')
    def validate_kind(self):
        if self.kind in ('expense', 'transfer') and self.amount >= 0:
            raise ValueError('expense_and_transfer_require_negative_amount')
        if self.kind in ('income', 'refund') and self.amount <= 0:
            raise ValueError('income_and_refund_require_positive_amount')
        if self.amount == 0:
            raise ValueError('zero_transaction')
        if (self.kind == 'transfer') != (self.to_account_id is not None):
            raise ValueError('transfer_requires_destination_only')
        return self


class TransactionPatch(Model):
    category: Name | None = None
    description: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    splits: list[Split] | None = Field(default=None, max_length=20)


class Connect(Idempotent):
    connector_id: Name


class Sync(Idempotent):
    outcome: Literal['success', 'failure'] = 'success'


class StatementMapping(Model):
    date: Name
    merchant: Name
    description: Name | None = None
    amount: Name | None = None
    debit: Name | None = None
    credit: Name | None = None
    currency: Name | None = None
    source_id: Name | None = None
    kind: Name | None = None
    category: Name | None = None

    @model_validator(mode='after')
    def amount_columns(self):
        if bool(self.amount) == bool(self.debit or self.credit):
            raise ValueError('map_amount_or_debit_credit')
        columns = [value for value in self.model_dump().values() if value is not None]
        if len(columns) != len(set(columns)):
            raise ValueError('duplicate_column_mapping')
        return self


class ImportPreview(Model):
    account_id: Name
    csv: str = Field(min_length=1, max_length=1_000_000)
    mode: Literal['legacy', 'statement'] = 'legacy'
    delimiter: Literal[',', ';', '\t'] = ','
    header_row: int = Field(default=1, ge=1, le=50)
    date_format: Literal['YMD', 'DMY', 'MDY'] = 'YMD'
    decimal_separator: Literal['.', ','] = '.'
    mapping: StatementMapping | None = None
    positive_kind: Literal['income', 'refund', 'adjustment'] | None = None
    file_name: str | None = Field(default=None, max_length=240)


class ImportDecision(Model):
    line: int = Field(ge=1)
    action: Literal['import', 'skip']


class ImportCommit(Idempotent):
    preview_digest: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    decisions: list[ImportDecision] = Field(default_factory=list, max_length=2_000)
