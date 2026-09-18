"""Money math Argus owns, in Python, under unit tests (operating rule 6).

Every function here is pure: typed inputs in, a typed answer or a typed
``NoSolution`` out, never an exception for an input that has no answer and
never a guess. Money amounts carry their currency. Nothing here reads a
message, calls a provider or formats prose.
"""

from argus.domain.finance.money import Money
from argus.domain.finance.outcomes import NoSolution

__all__ = ["Money", "NoSolution"]
