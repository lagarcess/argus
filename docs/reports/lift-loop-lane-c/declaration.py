"""Local-only tool declaration. No runtime consumer or model-facing schema.

The Python signature and compute validation own the five inputs and domain.
This is a single concrete declaration, not a universal input schema.
"""

from card import build_card
from compute import solve_for_unknown

DECLARATION = {
    "tool": solve_for_unknown.__name__,
    "compute": solve_for_unknown,
    "card": build_card,
    "confirmation": "answer_first",
    "external_calls": 0,
    "payment_timing": "end_of_period",
    "rate_basis": "effective_per_payment_period",
    "money_unit": "one_caller_supplied_currency",
    "cash_flow_signs": "received_positive_paid_negative",
}
