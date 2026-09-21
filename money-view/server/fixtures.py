"""Clearly synthetic, reproducible Clara demo data."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from .models import (
    DepositRate,
    InflationRate,
    PlacementInputs,
    RateDataset,
    Source,
    dataset_content_id,
)

Scenario = Literal[
    "baseline",
    "same_winner",
    "leader_changed",
    "inflation_crossed",
    "failure",
]

SCENARIOS: tuple[Scenario, ...] = (
    "baseline",
    "same_winner",
    "leader_changed",
    "inflation_crossed",
    "failure",
)

_RETRIEVED_AT = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
_SCENARIO_DATES = {
    "baseline": date(2026, 9, 15),
    "same_winner": date(2026, 9, 16),
    "leader_changed": date(2026, 9, 17),
    "inflation_crossed": date(2026, 9, 18),
}

_COUNTRIES = [
    {
        "code": "DO",
        "names": {
            "es-419": "República Dominicana",
            "en": "Dominican Republic",
        },
        "currencies": ["DOP", "USD"],
    },
    {
        "code": "NZ",
        "names": {
            "es-419": "Nueva Zelanda (demostración sintética)",
            "en": "New Zealand (synthetic demo)",
        },
        "currencies": ["NZD"],
    },
]

_COUNTRY_CONFIG = {
    "DO": {
        "currency": "DOP",
        "savings_institution": "Banco Brisa de Prueba (sintético)",
        "certificate_institution": "Cooperativa Faro de Prueba (sintética)",
        "baseline": ("6.20", "7.80", "4.00"),
        "same_winner": ("6.45", "7.90", "4.00"),
        "leader_changed": ("8.40", "7.90", "4.00"),
        "inflation_crossed": ("6.20", "7.80", "6.10"),
        "certificate_fee": "600",
    },
    "NZ": {
        "currency": "NZD",
        "savings_institution": "Aotearoa Example Bank (synthetic)",
        "certificate_institution": "Koru Fictional Credit Union (synthetic)",
        "baseline": ("4.25", "4.85", "2.40"),
        "same_winner": ("4.40", "4.90", "2.40"),
        "leader_changed": ("5.25", "4.90", "2.40"),
        "inflation_crossed": ("4.25", "4.85", "3.50"),
        "certificate_fee": "24",
    },
}

_DO_USD_CONFIG = {
    "baseline": ("3.20", "4.10", "2.50"),
    "same_winner": ("3.35", "4.20", "2.50"),
    "leader_changed": ("4.60", "4.20", "2.50"),
    "inflation_crossed": ("3.20", "4.10", "3.00"),
}


class FixtureError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail or code)


def _source(country: str, scenario: str, fact: str, title: str) -> Source:
    source_id = f"fixture-{country.lower()}-{scenario}-{fact}"
    return Source(
        id=source_id,
        title=f"Clara synthetic fixture: {title}",
        url=f"/api/sources/{source_id}",
        published_on=_SCENARIO_DATES[scenario],
        retrieved_at=_RETRIEVED_AT,
        kind="synthetic",
    )


def _make_dataset(country: str, scenario: str) -> RateDataset:
    config = _COUNTRY_CONFIG[country]
    savings_rate, certificate_rate, inflation_rate = config[scenario]
    currency = str(config["currency"])
    published_on = _SCENARIO_DATES[scenario]

    savings_source = _source(country, scenario, "savings", "savings rate")
    certificate_source = _source(
        country, scenario, "certificate", "180-day certificate rate"
    )
    inflation_source = _source(country, scenario, "inflation", "inflation illustration")

    rates = [
        DepositRate(
            id=f"{country.lower()}-savings",
            country=country,
            institution=str(config["savings_institution"]),
            product_type="savings",
            currency=currency,
            annual_rate_pct=Decimal(savings_rate),
            rate_basis="simple_annual",
            term_days=None,
            source=savings_source,
            annual_fee=None,
            fee_source=None,
        ),
        DepositRate(
            id=f"{country.lower()}-certificate-180",
            country=country,
            institution=str(config["certificate_institution"]),
            product_type="certificate",
            currency=currency,
            annual_rate_pct=Decimal(certificate_rate),
            rate_basis="simple_annual",
            term_days=180,
            source=certificate_source,
            annual_fee=Decimal(str(config["certificate_fee"])),
            fee_source=certificate_source,
        ),
    ]
    inflation = [
        InflationRate(
            country=country,
            currency=currency,
            annual_rate_pct=Decimal(inflation_rate),
            source=inflation_source,
        )
    ]
    if country == "DO":
        usd_savings_rate, usd_certificate_rate, usd_inflation_rate = _DO_USD_CONFIG[
            scenario
        ]
        usd_savings_source = _source(
            country, scenario, "usd-savings", "USD savings rate"
        )
        usd_certificate_source = _source(
            country, scenario, "usd-certificate", "180-day USD certificate rate"
        )
        usd_inflation_source = _source(
            country, scenario, "usd-inflation", "USD inflation illustration"
        )
        rates.extend(
            [
                DepositRate(
                    id="do-usd-savings",
                    country="DO",
                    institution="Banco Brisa USD de Prueba (sintético)",
                    product_type="savings",
                    currency="USD",
                    annual_rate_pct=Decimal(usd_savings_rate),
                    source=usd_savings_source,
                ),
                DepositRate(
                    id="do-usd-certificate-180",
                    country="DO",
                    institution="Cooperativa Faro USD de Prueba (sintética)",
                    product_type="certificate",
                    currency="USD",
                    annual_rate_pct=Decimal(usd_certificate_rate),
                    term_days=180,
                    source=usd_certificate_source,
                    annual_fee=Decimal("5"),
                    fee_source=usd_certificate_source,
                ),
            ]
        )
        inflation.append(
            InflationRate(
                country="DO",
                currency="USD",
                annual_rate_pct=Decimal(usd_inflation_rate),
                source=usd_inflation_source,
            )
        )
    payload: dict[str, object] = {
        "country": country,
        "label": f"Clara {country} {scenario} synthetic fixture",
        "rates": [rate.model_dump(mode="json") for rate in rates],
        "inflation": [item.model_dump(mode="json") for item in inflation],
        "published_on": published_on.isoformat(),
        "synthetic": True,
    }
    dataset = RateDataset(id="pending-content-hash", **payload)
    return dataset.model_copy(update={"id": dataset_content_id(dataset)})


def _example_source(
    example_id: str,
    inputs: PlacementInputs,
) -> dict[str, object]:
    source_id = f"fixture-example-{example_id}"
    return {
        "id": source_id,
        "title": "Clara synthetic fixture: sample user inputs",
        "url": f"/api/sources/{source_id}",
        "published_on": _SCENARIO_DATES["baseline"].isoformat(),
        "retrieved_at": _RETRIEVED_AT.isoformat().replace("+00:00", "Z"),
        "kind": "synthetic",
        "synthetic": True,
        "raw_inputs": inputs.model_dump(mode="json"),
    }


def get_countries() -> list[dict[str, object]]:
    return deepcopy(_COUNTRIES)


def get_examples() -> list[dict[str, object]]:
    do_inputs = PlacementInputs(
        amount=Decimal("250000"),
        currency="DOP",
        horizon_days=180,
        country="DO",
        current_annual_rate_pct=Decimal("5.25"),
    )
    nz_inputs = PlacementInputs(
        amount=Decimal("12000"),
        currency="NZD",
        horizon_days=365,
        country="NZ",
        current_annual_rate_pct=Decimal("3.00"),
    )
    return [
        {
            "id": "do-180-day-placement",
            "messages": {
                "es-419": "Quiero comparar RD$250,000 durante 180 días.",
                "en": "I want to compare DOP 250,000 for 180 days.",
            },
            "inputs": do_inputs.model_dump(mode="json"),
            "source": _example_source("do-180-day-placement", do_inputs),
        },
        {
            "id": "nz-365-day-placement",
            "messages": {
                "es-419": "Quiero comparar NZD 12,000 durante 365 días.",
                "en": "I want to compare NZD 12,000 for 365 days.",
            },
            "inputs": nz_inputs.model_dump(mode="json"),
            "source": _example_source("nz-365-day-placement", nz_inputs),
        },
    ]


def _source_documents() -> dict[str, dict[str, object]]:
    documents: dict[str, dict[str, object]] = {}
    for example in get_examples():
        source = example["source"]
        assert isinstance(source, dict)
        documents[str(source["id"])] = deepcopy(source)

    for country in _COUNTRY_CONFIG:
        for scenario in SCENARIOS:
            if scenario == "failure":
                continue
            dataset = _make_dataset(country, scenario)
            for rate in dataset.rates:
                rate_document = rate.source.model_dump(mode="json") | {
                    "synthetic": True,
                    "raw_inputs": {
                        "country": rate.country,
                        "currency": rate.currency,
                        "institution": rate.institution,
                        "product_type": rate.product_type,
                        "annual_rate_pct": str(rate.annual_rate_pct),
                        "rate_basis": rate.rate_basis,
                        "term_days": rate.term_days,
                        "annual_fee": (
                            str(rate.annual_fee) if rate.annual_fee is not None else None
                        ),
                    },
                }
                documents[rate.source.id] = rate_document
            for inflation in dataset.inflation:
                documents[inflation.source.id] = inflation.source.model_dump(
                    mode="json"
                ) | {
                    "synthetic": True,
                    "raw_inputs": {
                        "country": inflation.country,
                        "currency": inflation.currency,
                        "annual_rate_pct": str(inflation.annual_rate_pct),
                        "model": "constant_geometric_annual_illustration",
                    },
                }
    return documents


def get_source_document(source_id: str) -> dict[str, object] | None:
    document = _source_documents().get(source_id)
    return deepcopy(document) if document is not None else None


class FixtureProvider:
    """Explicit synthetic provider; it never impersonates a real source."""

    def __init__(self, scenario: Scenario = "baseline") -> None:
        if scenario not in SCENARIOS:
            raise FixtureError("unknown_fixture_scenario", scenario)
        self.scenario = scenario

    def fetch(self, country: str) -> RateDataset:
        normalized_country = country.upper()
        if normalized_country not in _COUNTRY_CONFIG:
            raise FixtureError(
                "unsupported_country",
                f"No Clara fixture dataset covers {normalized_country}",
            )
        if self.scenario == "failure":
            raise FixtureError(
                "synthetic_load_failure",
                "This fixture deliberately simulates a failed data load",
            )
        return _make_dataset(normalized_country, self.scenario)
