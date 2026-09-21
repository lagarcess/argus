from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from server.calculator import calculate
from server.fixtures import (
    SCENARIOS,
    FixtureError,
    FixtureProvider,
    get_countries,
    get_examples,
    get_source_document,
)
from server.models import PlacementInputs, dataset_content_id
from server.providers import (
    BCRDProvider,
    ProviderDataIncompleteError,
    ProviderPayloadError,
    ProviderUnavailableError,
    RateProvider,
    SBDepositRecord,
    SBProvider,
    normalize_sb_record,
    parse_sb_records,
)

NOW = datetime(2026, 9, 20, 15, 30, tzinfo=timezone.utc)


class _Response:
    def __init__(self, payload: object, *, has_next: bool) -> None:
        self._payload = payload
        self.headers = {"x-pagination": json.dumps({"HasNext": has_next})}

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        return None


class _Client:
    def __init__(self, responses: list[_Response] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict[str, object]] = []

    def get(
        self,
        url: str,
        *,
        params: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> _Response:
        self.calls.append(
            {"url": url, "params": params, "headers": headers, "timeout": timeout}
        )
        return self.responses.pop(0)


def _sb_row(rate: float = 7.125) -> dict[str, object]:
    return {
        "periodo": "2026-08",
        "tipoEntidad": "BM",
        "entidad": "ENTIDAD DE PRUEBA",
        "region": "NORTE",
        "provincia": "SANTIAGO",
        "persona": "Persona Fisica",
        "genero": None,
        "tipoCliente": "PUBLICO GENERAL",
        "instrumentoCaptacion": "CERTIFICADOS FINANCIEROS",
        "moneda": "PESO DOMINICANO",
        "divisa": "DOP",
        "partidaNivel1": None,
        "partidaNivel2": None,
        "publicoPrivadoNivel1": None,
        "publicoPrivadoNivel2": None,
        "financieroNoFinanciero": None,
        "residenteNoResidente": None,
        "componente": None,
        "instrumentoMedio": None,
        "contraParte": None,
        "situacionNivel1": None,
        "situacionNivel2": None,
        "cantidadInstrumento": 10,
        "balance": 1250000.50,
        "tasaPrimedioPonderadoPorBalance": rate,
        "tasaPrimedioPonderado": 6.900,
    }


def test_fixture_provider_satisfies_provider_protocol_and_has_two_countries() -> None:
    provider = FixtureProvider()

    assert isinstance(provider, RateProvider)
    assert get_countries() == [
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
    assert provider.fetch("DO").country == "DO"
    assert provider.fetch("NZ").country == "NZ"


def test_fixture_dataset_identity_is_a_content_hash() -> None:
    dataset = FixtureProvider().fetch("DO")

    assert len(dataset.id) == 64
    assert dataset.id == dataset_content_id(dataset)


def test_fixture_dataset_identity_excludes_retrieval_timestamps() -> None:
    dataset = FixtureProvider().fetch("DO")
    later = datetime(2026, 9, 21, 9, 0, tzinfo=timezone.utc)
    rates = []
    for rate in dataset.rates:
        source = rate.source.model_copy(update={"retrieved_at": later})
        fee_source = source if rate.fee_source is not None else None
        rates.append(
            rate.model_copy(update={"source": source, "fee_source": fee_source})
        )
    inflation = [
        item.model_copy(
            update={
                "source": item.source.model_copy(update={"retrieved_at": later})
            }
        )
        for item in dataset.inflation
    ]
    observed_later = dataset.model_copy(update={"rates": rates, "inflation": inflation})

    assert dataset_content_id(observed_later) == dataset.id


def test_fixture_scenarios_keep_product_ids_stable_across_publications() -> None:
    baseline = FixtureProvider("baseline").fetch("DO")
    changed = FixtureProvider("leader_changed").fetch("DO")

    assert [rate.id for rate in baseline.rates] == [
        "do-savings",
        "do-certificate-180",
        "do-usd-savings",
        "do-usd-certificate-180",
    ]
    assert [rate.id for rate in changed.rates] == [
        "do-savings",
        "do-certificate-180",
        "do-usd-savings",
        "do-usd-certificate-180",
    ]
    assert baseline.rates[0].source.id == "fixture-do-baseline-savings"
    assert changed.rates[0].source.id == "fixture-do-leader_changed-savings"


def test_fixture_scenarios_change_the_observable_winner_only_when_intended() -> None:
    inputs = PlacementInputs(
        amount="250000",
        currency="DOP",
        horizon_days=180,
        country="DO",
        current_annual_rate_pct="5.25",
    )

    baseline = calculate(
        inputs,
        FixtureProvider("baseline").fetch("DO"),
        comparison_id="baseline",
        created_at=NOW,
    )
    same = calculate(
        inputs,
        FixtureProvider("same_winner").fetch("DO"),
        comparison_id="same",
        created_at=NOW,
    )
    changed = calculate(
        inputs,
        FixtureProvider("leader_changed").fetch("DO"),
        comparison_id="changed",
        created_at=NOW,
    )

    assert baseline.winner_ids == ["deposit:do-certificate-180"]
    assert same.winner_ids == ["deposit:do-certificate-180"]
    assert changed.winner_ids == ["deposit:do-savings"]


def test_usd_is_supported_without_adding_a_us_country_provider() -> None:
    inputs = PlacementInputs(
        amount="10000",
        currency="USD",
        horizon_days=180,
        country="DO",
        current_annual_rate_pct="2.00",
    )

    result = calculate(
        inputs,
        FixtureProvider().fetch("DO"),
        comparison_id="do-usd",
        created_at=NOW,
    )

    assert [row.id for row in result.rows] == [
        "cash",
        "deposit:do-usd-savings",
        "deposit:do-usd-certificate-180",
    ]
    assert result.inflation.currency == "USD"
    with pytest.raises(FixtureError) as error:
        FixtureProvider().fetch("US")
    assert error.value.code == "unsupported_country"


def test_inflation_crossed_fixture_crosses_the_demo_current_rate() -> None:
    baseline = FixtureProvider("baseline").fetch("DO")
    crossed = FixtureProvider("inflation_crossed").fetch("DO")

    assert baseline.inflation[0].annual_rate_pct == Decimal("4.00")
    assert crossed.inflation[0].annual_rate_pct == Decimal("6.10")
    assert Decimal("4.00") <= Decimal("5.25") < Decimal("6.10")


def test_failure_and_unsupported_country_never_fall_back_to_other_data() -> None:
    assert "failure" in SCENARIOS
    with pytest.raises(FixtureError) as failure:
        FixtureProvider("failure").fetch("DO")
    with pytest.raises(FixtureError) as unsupported:
        FixtureProvider().fetch("US")

    assert failure.value.code == "synthetic_load_failure"
    assert unsupported.value.code == "unsupported_country"


def test_every_fixture_numeric_source_has_url_date_and_raw_receipt() -> None:
    source_ids: set[str] = set()
    for country in ("DO", "NZ"):
        for scenario in ("baseline", "same_winner", "leader_changed", "inflation_crossed"):
            dataset = FixtureProvider(scenario).fetch(country)
            source_ids.update(rate.source.id for rate in dataset.rates)
            source_ids.update(
                rate.fee_source.id
                for rate in dataset.rates
                if rate.fee_source is not None
            )
            source_ids.update(item.source.id for item in dataset.inflation)
    source_ids.update(str(example["source"]["id"]) for example in get_examples())

    documents = [get_source_document(source_id) for source_id in source_ids]

    assert all(document is not None for document in documents)
    assert all(document["url"].startswith("/api/sources/") for document in documents)
    assert all(document["published_on"].startswith("2026-09-") for document in documents)
    assert all(document["kind"] == "synthetic" for document in documents)
    assert all(document["synthetic"] is True for document in documents)
    assert all(document["raw_inputs"] for document in documents)
    assert get_source_document("unknown") is None


def test_sb_parser_preserves_the_documented_primedio_wire_field() -> None:
    record = parse_sb_records([_sb_row()])[0]
    normalized = normalize_sb_record(record, retrieved_at=NOW)

    assert record.tasaPrimedioPonderadoPorBalance == Decimal("7.125")
    assert normalized.average_rate_paid_on_balances == Decimal("7.125")
    assert normalized.effective_period == "2026-08"
    assert normalized.validation_issues == [
        "missing_maturity",
        "unknown_rate_unit",
        "unknown_annualization",
        "missing_publication_date",
    ]


@pytest.mark.parametrize(
    "quantity",
    [True, "10", 1.0, -1, 2147483648],
)
def test_sb_parser_requires_nonnegative_strict_int32_quantity(quantity: object) -> None:
    row = _sb_row()
    row["cantidadInstrumento"] = quantity

    with pytest.raises(ProviderPayloadError) as error:
        parse_sb_records([row])

    assert error.value.code == "invalid_sb_record"


@pytest.mark.parametrize(
    "field",
    ["balance", "tasaPrimedioPonderadoPorBalance", "tasaPrimedioPonderado"],
)
@pytest.mark.parametrize("value", [True, "7.125"])
def test_sb_parser_accepts_only_json_numbers_for_numeric_fields(
    field: str,
    value: object,
) -> None:
    row = _sb_row()
    row[field] = value

    with pytest.raises(ProviderPayloadError) as error:
        parse_sb_records([row])

    assert error.value.code == "invalid_sb_record"


def test_sb_parser_rejects_corrected_but_undocumented_field_name() -> None:
    row = _sb_row()
    row["tasaPromedioPonderadoPorBalance"] = row.pop(
        "tasaPrimedioPonderadoPorBalance"
    )

    with pytest.raises(ProviderPayloadError) as error:
        parse_sb_records([row])

    assert error.value.code == "invalid_sb_record"


def test_sb_missing_key_fails_before_any_request() -> None:
    client = _Client()
    provider = SBProvider(
        subscription_key=None,
        period_start="2026-08",
        client=client,
    )

    with pytest.raises(ProviderUnavailableError) as error:
        provider.fetch("DO")

    assert error.value.code == "missing_sb_subscription_key"
    assert client.calls == []


def test_sb_raw_reader_uses_bounded_documented_pagination() -> None:
    client = _Client(
        [
            _Response([_sb_row(7.125)], has_next=True),
            _Response([_sb_row(7.250)], has_next=False),
        ]
    )
    provider = SBProvider(
        subscription_key="test-key",
        period_start="2026-08",
        client=client,
        max_pages=2,
        records_per_page=1,
    )

    rows = provider.fetch_raw("DO")

    assert [row.average_rate_paid_on_balances for row in rows] == [
        Decimal("7.125"),
        Decimal("7.250"),
    ]
    assert [call["params"]["paginas"] for call in client.calls] == [1, 2]
    assert all(call["params"]["periodoInicial"] == "2026-08" for call in client.calls)


def test_sb_reader_stops_instead_of_truncating_when_page_bound_is_reached() -> None:
    client = _Client([_Response([_sb_row()], has_next=True)])
    provider = SBProvider(
        subscription_key="test-key",
        period_start="2026-08",
        client=client,
        max_pages=1,
    )

    with pytest.raises(ProviderPayloadError) as error:
        provider.fetch_raw("DO")

    assert error.value.code == "sb_pagination_limit_reached"


def test_sb_provider_refuses_to_turn_raw_rows_into_calculation_data() -> None:
    client = _Client([_Response([_sb_row()], has_next=False)])
    provider = SBProvider(
        subscription_key="test-key",
        period_start="2026-08",
        client=client,
    )

    with pytest.raises(ProviderDataIncompleteError) as error:
        provider.fetch("DO")

    assert error.value.code == "sb_not_calculation_ready"
    assert "maturity" in error.value.detail
    assert "publication date" in error.value.detail


def test_sb_raw_schema_keeps_every_documented_field_optional() -> None:
    record = SBDepositRecord.model_validate({})

    assert record.model_dump() == {
        "periodo": None,
        "tipoEntidad": None,
        "entidad": None,
        "region": None,
        "provincia": None,
        "persona": None,
        "genero": None,
        "tipoCliente": None,
        "instrumentoCaptacion": None,
        "moneda": None,
        "divisa": None,
        "partidaNivel1": None,
        "partidaNivel2": None,
        "publicoPrivadoNivel1": None,
        "publicoPrivadoNivel2": None,
        "financieroNoFinanciero": None,
        "residenteNoResidente": None,
        "componente": None,
        "instrumentoMedio": None,
        "contraParte": None,
        "situacionNivel1": None,
        "situacionNivel2": None,
        "cantidadInstrumento": None,
        "balance": None,
        "tasaPrimedioPonderadoPorBalance": None,
        "tasaPrimedioPonderado": None,
    }


def test_bcrd_is_explicitly_unavailable_without_an_invented_endpoint() -> None:
    with pytest.raises(ProviderUnavailableError) as error:
        BCRDProvider().fetch("DO")

    assert error.value.code == "bcrd_schema_unverified"
    assert "endpoint" in error.value.detail
