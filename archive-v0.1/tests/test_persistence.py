import base64
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from argus.domain.persistence import PersistenceService
from argus.engine import EngineBacktestResults


def test_persistence_service_init_no_supabase(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "")
    service = PersistenceService()
    assert service.client is None


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_persistence_service_init_invalid_url_does_not_raise(
    mock_get_settings, mock_create_client
):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "not-a-valid-url"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "service-role-key"
    mock_get_settings.return_value = mock_settings
    mock_create_client.side_effect = Exception("Invalid URL")

    service = PersistenceService()

    assert service.client is None


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_save_strategy_success(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_upsert = MagicMock()
    mock_upsert.execute.return_value.data = [{"id": "123", "name": "Test"}]
    mock_table = MagicMock()
    mock_table.upsert.return_value = mock_upsert
    mock_supabase.return_value.table.return_value = mock_table

    strategy_data = {
        "name": "Test",
        "symbols": ["BTC/USD"],
        "timeframe": "1h",
        "start_date": None,
        "end_date": None,
    }

    result = service.save_strategy("user1", strategy_data)
    assert result is not None
    assert result["id"] == "123"


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_save_strategy_error(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_upsert = MagicMock()
    mock_upsert.execute.side_effect = Exception("DB error")
    mock_table = MagicMock()
    mock_table.upsert.return_value = mock_upsert
    mock_supabase.return_value.table.return_value = mock_table

    result = service.save_strategy("user1", {"name": "Test"})
    assert result is None


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_get_strategy_success(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_execute = MagicMock()
    mock_execute.data = {"id": "123", "name": "Test"}
    mock_single = MagicMock()
    mock_single.execute.return_value = mock_execute
    mock_eq2 = MagicMock()
    mock_eq2.single.return_value = mock_single
    mock_eq1 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_select = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_table = MagicMock()
    mock_table.select.return_value = mock_select
    mock_supabase.return_value.table.return_value = mock_table

    result = service.get_strategy("123", "user1")
    assert result is not None
    assert result["id"] == "123"


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_delete_strategy(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_execute = MagicMock()
    mock_execute.data = [{"id": "123"}]
    mock_is = MagicMock()
    mock_is.execute.return_value = mock_execute
    mock_eq2 = MagicMock()
    mock_eq2.is_.return_value = mock_is
    mock_eq1 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_delete = MagicMock()
    mock_delete.eq.return_value = mock_eq1
    mock_table = MagicMock()
    mock_table.delete.return_value = mock_delete
    mock_supabase.return_value.table.return_value = mock_table

    result = service.delete_strategy("123", "user1")
    assert result is True


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_list_strategies(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_execute = MagicMock()
    mock_execute.data = [{"id": "1", "created_at": "2025-01-01T00:00:00Z"}]
    mock_limit = MagicMock()
    mock_limit.execute.return_value = mock_execute
    mock_order2 = MagicMock()
    mock_order2.limit.return_value = mock_limit
    mock_order1 = MagicMock()
    mock_order1.order.return_value = mock_order2
    mock_eq = MagicMock()
    mock_eq.order.return_value = mock_order1
    mock_select = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_table = MagicMock()
    mock_table.select.return_value = mock_select
    mock_supabase.return_value.table.return_value = mock_table

    strategies, cursor = service.list_strategies("user1", limit=1)
    assert len(strategies) == 1
    assert cursor is not None


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_save_simulation(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_insert = MagicMock()
    mock_insert.execute.return_value.data = [{"id": "sim_123"}]
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_insert
    mock_supabase.return_value.table.return_value = mock_table

    mock_result = EngineBacktestResults(
        total_return_pct=14.5,
        win_rate=62.0,
        sharpe_ratio=1.8,
        sortino_ratio=2.1,
        calmar_ratio=1.2,
        profit_factor=1.5,
        expectancy=0.05,
        max_drawdown_pct=0.05,
        equity_curve=[100.0, 114.5],
        trades=[],
        reality_gap_metrics={"slippage_impact_pct": 1.2, "fee_impact_pct": 0.4},
        pattern_breakdown={},
    )

    sim_id = service.save_simulation("user1", "strat1", ["BTC"], "1h", mock_result, {})
    assert sim_id == "sim_123"

    inserted_payload = mock_table.insert.call_args[0][0]
    assert inserted_payload["symbol"] == "BTC"
    assert inserted_payload["symbols"] == ["BTC"]


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_save_telemetry_event(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_insert = MagicMock()
    mock_insert.execute.return_value.data = [{"id": "evt_123"}]
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_insert
    mock_supabase.return_value.table.return_value = mock_table

    saved = service.save_telemetry_event(
        user_id="user1",
        event="draft_success",
        event_ts=datetime.now(timezone.utc),
        properties={"source": "unit-test"},
    )
    assert saved is True


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_telemetry_row_persists_via_insert_execute(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_insert = MagicMock()
    mock_insert.execute.return_value.data = [{"id": "evt_321"}]
    mock_table = MagicMock()
    mock_table.insert.return_value = mock_insert
    mock_supabase.return_value.table.return_value = mock_table

    payload_ts = datetime(2026, 4, 17, 12, 0, tzinfo=timezone.utc)
    saved = service.save_telemetry_event(
        user_id="550e8400-e29b-41d4-a716-446655440000",
        event="backtest_success",
        event_ts=payload_ts,
        properties={"source": "telemetry-test"},
        strict=True,
    )

    assert saved is True
    mock_table.insert.assert_called_once()
    mock_insert.execute.assert_called_once()


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_get_user_simulations(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_count = MagicMock()
    mock_count.execute.return_value.count = 10

    mock_range = MagicMock()
    mock_range.execute.return_value.data = [
        {
            "id": "sim1",
            "symbols": ["BTC/USD"],
            "timeframe": "1h",
            "created_at": "2025-01-01T00:00:00Z",
            "summary": {"total_return_pct": 5.0},
            "strategies": {"name": "Test Strat"},
        }
    ]
    mock_limit = MagicMock()
    mock_limit.or_.return_value = mock_limit
    mock_limit.execute.return_value.data = [
        {
            "id": "sim1",
            "symbols": ["BTC/USD"],
            "timeframe": "1h",
            "created_at": "2025-01-01T00:00:00Z",
            "summary": {"total_return_pct": 5.0},
            "strategies": {"name": "Test Strat"},
        }
    ]
    mock_order2 = MagicMock()
    mock_order2.limit.return_value = mock_limit
    mock_order1 = MagicMock()
    mock_order1.order.return_value = mock_order2
    mock_eq2 = MagicMock()
    mock_eq2.order.return_value = mock_order1
    mock_select2 = MagicMock()
    mock_select2.eq.return_value = mock_eq2

    def table_side_effect(name):
        mock = MagicMock()
        if name == "simulations":
            # For the count query vs the range query, we need to differentiate based on the select args.
            # But magicmock makes it tricky, let's just return a mock that handles both.
            def select_side_effect(*args, **kwargs):
                if kwargs.get("count") == "exact":
                    mock_eq1 = MagicMock()
                    mock_eq1.eq.return_value = mock_count
                    return mock_eq1
                return mock_select2

            mock.select.side_effect = select_side_effect
        return mock

    mock_supabase.return_value.table.side_effect = table_side_effect

    summaries, total, next_cursor = service.get_user_simulations("user1", limit=1)
    assert total == 10
    assert len(summaries) == 1
    assert summaries[0]["id"] == "sim1"
    assert next_cursor is not None


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_get_user_simulations_accepts_json_cursor(mock_get_settings, mock_supabase):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_count = MagicMock()
    mock_count.execute.return_value.count = 1

    mock_limit = MagicMock()
    mock_limit.or_.return_value = mock_limit
    mock_limit.execute.return_value.data = [
        {
            "id": "sim2",
            "symbols": ["BTC/USD"],
            "timeframe": "1h",
            "created_at": "2026-04-07T13:15:00+00:00",
            "summary": {"total_return_pct": 5.0},
            "strategies": {"name": "Test Strat"},
        }
    ]
    mock_order2 = MagicMock()
    mock_order2.limit.return_value = mock_limit
    mock_order1 = MagicMock()
    mock_order1.order.return_value = mock_order2
    mock_eq2 = MagicMock()
    mock_eq2.order.return_value = mock_order1
    mock_select2 = MagicMock()
    mock_select2.eq.return_value = mock_eq2

    def table_side_effect(name):
        mock = MagicMock()
        if name == "simulations":

            def select_side_effect(*args, **kwargs):
                if kwargs.get("count") == "exact":
                    mock_eq1 = MagicMock()
                    mock_eq1.eq.return_value = mock_count
                    return mock_eq1
                return mock_select2

            mock.select.side_effect = select_side_effect
        return mock

    mock_supabase.return_value.table.side_effect = table_side_effect
    cursor = base64.b64encode(
        json.dumps(
            {"created_at": "2026-04-07T13:15:00+00:00", "id": "sim1"},
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("utf-8")

    summaries, total, next_cursor = service.get_user_simulations(
        "user1", limit=1, cursor=cursor
    )

    assert total == 1
    assert len(summaries) == 1
    assert next_cursor is not None


@patch("argus.domain.persistence.create_client")
@patch("argus.domain.persistence.get_settings")
def test_get_user_simulations_falls_back_to_legacy_symbol_column(
    mock_get_settings, mock_supabase
):
    mock_settings = MagicMock()
    mock_settings.SUPABASE_URL = "test"
    mock_settings.SUPABASE_SERVICE_ROLE_KEY = "test"
    mock_get_settings.return_value = mock_settings
    service = PersistenceService()

    mock_count = MagicMock()
    mock_count.execute.return_value.count = 1

    # First query (symbols) fails, second query (symbol) succeeds.

    symbols_query = MagicMock()
    symbols_query.eq.return_value = symbols_query
    symbols_query.order.return_value = symbols_query
    symbols_query.limit.return_value = symbols_query
    symbols_query.execute.side_effect = Exception(
        "column simulations.symbols does not exist"
    )

    symbol_query = MagicMock()
    symbol_query.eq.return_value = symbol_query
    symbol_query.order.return_value = symbol_query
    symbol_query.limit.return_value = symbol_query
    symbol_query.execute.return_value.data = [
        {
            "id": "sim_legacy",
            "symbol": "AAPL",
            "timeframe": "1h",
            "created_at": "2026-04-07T13:15:00+00:00",
            "summary": {"total_return_pct": 5.0},
            "reality_gap_metrics": {"fidelity_score": 0.9},
            "strategies": {"name": "Legacy Strat"},
        }
    ]

    def table_side_effect(name):
        if name != "simulations":
            return MagicMock()
        table_instance = MagicMock()

        def select_side_effect(*args, **kwargs):
            if kwargs.get("count") == "exact":
                count_select = MagicMock()
                count_select.eq.return_value = mock_count
                return count_select
            select_clause = args[0]
            if " symbols," in select_clause:
                return symbols_query
            return symbol_query

        table_instance.select.side_effect = select_side_effect
        return table_instance

    mock_supabase.return_value.table.side_effect = table_side_effect

    summaries, total, _ = service.get_user_simulations("user1", limit=1)

    assert total == 1
    assert len(summaries) == 1
    assert summaries[0]["symbols"] == ["AAPL"]


def _build_fake_persistence_service() -> PersistenceService:
    class FakeResponse:
        def __init__(self, data=None, count=None):
            self.data = data or []
            self.count = count

    class FakeQuery:
        def __init__(self, table_name, storage):
            self.table_name = table_name
            self.storage = storage
            self._limit = None
            self._count_mode = None

        def upsert(self, payload):
            existing = next(
                (
                    row
                    for row in self.storage[self.table_name]
                    if row.get("id") == payload.get("id")
                ),
                None,
            )
            if existing:
                existing.update(payload)
                self._result = [existing]
            else:
                self.storage[self.table_name].append(payload)
                self._result = [payload]
            return self

        def insert(self, payload):
            if isinstance(payload, dict):
                self.storage[self.table_name].append(payload)
                self._result = [payload]
            else:
                self.storage[self.table_name].extend(payload)
                self._result = payload
            return self

        def select(self, *args, **kwargs):
            self._count_mode = kwargs.get("count")
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def limit(self, n):
            self._limit = n
            return self

        def or_(self, *_args, **_kwargs):
            return self

        def execute(self):
            if hasattr(self, "_result"):
                return FakeResponse(self._result)

            rows = list(self.storage[self.table_name])
            if self._count_mode == "exact":
                return FakeResponse(rows, count=len(rows))
            if self._limit is not None:
                rows = rows[: self._limit]
            if self.table_name == "simulations":
                rows = [
                    {**row, "strategies": {"name": "Golden Flow Strategy"}}
                    for row in rows
                ]
            return FakeResponse(rows)

    class FakeClient:
        def __init__(self):
            self.storage = {
                "strategies": [],
                "simulations": [],
                "telemetry_events": [],
            }

        def table(self, table_name):
            return FakeQuery(table_name, self.storage)

    service = PersistenceService()
    service.client = FakeClient()
    return service


def test_golden_flow_draft_save_persists_strategy_record():
    service = _build_fake_persistence_service()
    user_id = "00000000-0000-4000-8000-000000000001"
    strategy = service.save_strategy(
        user_id,
        {
            "name": "Golden Flow Strategy",
            "symbols": ["AAPL"],
            "timeframe": "1Hour",
            "entry_criteria": [{"indicator_a": "SMA_10", "operator": "gt", "value": 1}],
            "exit_criteria": [{"indicator_a": "SMA_10", "operator": "lt", "value": 1}],
            "indicators_config": {},
            "patterns": [],
        },
        strategy_id="strategy-1",
        strict=True,
    )

    assert strategy is not None
    assert strategy["id"] == "strategy-1"
    assert service.client.storage["strategies"][0]["user_id"] == user_id


def test_golden_flow_saved_simulation_is_returned_in_history(make_engine_results):
    service = _build_fake_persistence_service()
    user_id = "00000000-0000-4000-8000-000000000001"
    service.save_strategy(
        user_id,
        {
            "name": "Golden Flow Strategy",
            "symbols": ["AAPL"],
            "timeframe": "1Hour",
            "entry_criteria": [{"indicator_a": "SMA_10", "operator": "gt", "value": 1}],
            "exit_criteria": [{"indicator_a": "SMA_10", "operator": "lt", "value": 1}],
            "indicators_config": {},
            "patterns": [],
        },
        strategy_id="strategy-1",
        strict=True,
    )

    simulation_id = service.save_simulation(
        user_id=user_id,
        strategy_id="strategy-1",
        symbols=["AAPL"],
        timeframe="1Hour",
        result=make_engine_results(),
        config_snapshot={"name": "Golden Flow Strategy"},
        simulation_id="simulation-1",
    )
    assert simulation_id == "simulation-1"

    summaries, total, _ = service.get_user_simulations(user_id, strict=True)
    assert total == 1
    assert summaries[0]["id"] == "simulation-1"


def test_golden_flow_telemetry_event_persists_row():
    service = _build_fake_persistence_service()
    user_id = "00000000-0000-4000-8000-000000000001"
    saved = service.save_telemetry_event(
        user_id=user_id,
        event="draft_saved",
        event_ts=datetime(2026, 4, 17, tzinfo=timezone.utc),
        properties={"flow": "golden"},
        strict=True,
    )
    assert saved is True
    assert service.client.storage["telemetry_events"][0]["event"] == "draft_saved"
