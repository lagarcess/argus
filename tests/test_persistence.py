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
    mock_order = MagicMock()
    mock_order.range.return_value = mock_range
    mock_eq2 = MagicMock()
    mock_eq2.order.return_value = mock_order
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

    summaries, total = service.get_user_simulations("user1")
    assert total == 10
    assert len(summaries) == 1
    assert summaries[0]["id"] == "sim1"
