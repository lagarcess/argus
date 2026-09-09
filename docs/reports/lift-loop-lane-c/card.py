"""Throwaway typed card body, not a web component or production artifact."""


def build_card(*, inputs: dict[str, float | None], answer: float) -> dict:
    (unknown,) = (field for field, value in inputs.items() if value is None)
    return {
        "kind": "time_value_of_money",
        "version": 1,
        "answer": {"field": unknown, "value": answer},
        "inputs": dict(inputs),
    }
