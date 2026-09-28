"""Domain tables for the PROPOSED recording contract (test-only).

Account natures, activity leg signs and the default category catalog live here
as data, so rules read a table instead of branching on names.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal, Optional

AccountType = Literal[
    "cash",
    "checking",
    "savings",
    "investment",
    "credit_card",
    "other_debt",
    "property",
    "vehicle",
    "other_asset",
]
Nature = Literal["asset", "liability"]
Kind = Literal["expense", "income", "refund", "transfer", "debt_payment"]
Family = Literal["spending", "income"]

NATURE: Mapping[str, Nature] = {
    "cash": "asset",
    "checking": "asset",
    "savings": "asset",
    "investment": "asset",
    "credit_card": "liability",
    "other_debt": "liability",
    "property": "asset",
    "vehicle": "asset",
    "other_asset": "asset",
}
ESTIMATED_TYPES = frozenset({"property", "vehicle", "other_asset"})
LIQUID_TYPES = frozenset({"cash", "checking", "savings"})
REFUNDABLE_TYPES = frozenset({"cash", "checking", "savings", "credit_card"})


def signed_to_owner(typed_minor: int, account_type: str) -> int:
    """Project a typed amount owed/held into the owner-signed balance.

    The person types a debt as a positive amount owed; the server flips once.
    """
    return -typed_minor if NATURE[account_type] == "liability" else typed_minor


LEG_SIGNS: Mapping[str, tuple[int, Optional[int]]] = {
    "expense": (-1, None),
    "income": (1, None),
    "refund": (1, None),
    "transfer": (-1, 1),
    "debt_payment": (-1, 1),
}
COUNTER_NATURE: Mapping[str, Optional[str]] = {
    "transfer": None,
    "debt_payment": "liability",
}
KIND_FAMILY: Mapping[str, Optional[Family]] = {
    "expense": "spending",
    "refund": "spending",
    "income": "income",
    "transfer": None,
    "debt_payment": None,
}
TOTAL_BUCKET: Mapping[str, Optional[tuple[str, int]]] = {
    "expense": ("spending", 1),
    "refund": ("spending", -1),
    "income": ("income", 1),
    "transfer": None,
    "debt_payment": None,
}
NOTE_MAX = 200
NICKNAME_MAX = 60
CUSTOM_CATEGORY_MAX = 60
PERSONAL_SPACE = "personal"


@dataclass(frozen=True)
class Category:
    id: str
    family: Family
    labels: Mapping[str, str]
    space_id: Optional[str] = None


def _default(identifier: str, family: Family, en: str, es: str) -> Category:
    return Category(identifier, family, {"en": en, "es-419": es})


DEFAULT_CATEGORIES: Mapping[str, Category] = {
    item.id: item
    for item in (
        _default("groceries", "spending", "Groceries", "Supermercado"),
        _default("dining", "spending", "Dining", "Comida"),
        _default("transport", "spending", "Transport", "Transporte"),
        _default("housing", "spending", "Housing", "Vivienda"),
        _default("utilities", "spending", "Utilities", "Servicios"),
        _default("health", "spending", "Health", "Salud"),
        _default("shopping", "spending", "Shopping", "Compras"),
        _default("interest_charge", "spending", "Interest", "Intereses"),
        _default("fees", "spending", "Fees", "Comisiones"),
        _default("other_spending", "spending", "Other", "Otro"),
        _default("salary", "income", "Salary", "Salario"),
        _default("remittance", "income", "Remittance", "Remesa"),
        _default("interest_earned", "income", "Interest", "Intereses"),
        _default("other_income", "income", "Other income", "Otro ingreso"),
    )
}
