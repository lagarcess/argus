"""
Tests for BacktestArchivalPipeline (Issue #361).

Follows the canonical test_rejected_signal_archival.py fixture pattern.
Uses FactTheoreticalSignalFactory for test data and @pytest.mark.parametrize
for the 4 signal outcome paths.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from crypto_signals.domain.schemas import (
    AssetClass,
    AssetClassFee,
    OrderSide,
    SignalStatus,
)
from crypto_signals.pipelines.backtest_archival import (
    BacktestArchivalPipeline,
)

from tests.factories import FactTheoreticalSignalFactory

# =====================================================================
# Fixtures
# =====================================================================


@pytest.fixture
def mock_firestore():
    return MagicMock()


@pytest.fixture
def mock_market_provider():
    return MagicMock()


@pytest.fixture
def pipeline(mock_firestore, mock_market_provider):
    """Instantiate pipeline with all external deps patched."""
    with (
        patch(
            "crypto_signals.pipelines.backtest_archival.firestore.Client",
            return_value=mock_firestore,
        ),
        patch(
            "crypto_signals.pipelines.base.get_settings",
        ) as mock_get_settings,
        patch(
            "crypto_signals.pipelines.backtest_archival.MarketDataProvider",
            return_value=mock_market_provider,
        ),
        patch(
            "crypto_signals.pipelines.backtest_archival.get_stock_data_client",
            return_value=MagicMock(),
        ),
        patch(
            "crypto_signals.pipelines.backtest_archival.get_crypto_data_client",
            return_value=MagicMock(),
        ),
        patch("crypto_signals.pipelines.base.bigquery.Client") as mock_bq,
        patch("crypto_signals.pipelines.base.SchemaGuardian") as mock_guardian,
    ):
        mock_get_settings.return_value.GOOGLE_CLOUD_PROJECT = "test-project"
        mock_get_settings.return_value.ENVIRONMENT = "PROD"
        mock_get_settings.return_value.SCHEMA_GUARDIAN_STRICT_MODE = True

        pipe = BacktestArchivalPipeline()
        pipe.firestore_client = mock_firestore
        pipe.market_provider = mock_market_provider
        pipe.bq_client = mock_bq.return_value
        pipe.guardian = mock_guardian.return_value

        return pipe


# =====================================================================
# Helpers
# =====================================================================


def _make_raw_signal(
    *,
    signal_id: str = "sig_1",
    symbol: str = "BTC/USD",
    asset_class: str = AssetClass.CRYPTO.value,
    entry_price: float = 50000.0,
    suggested_stop: float = 48000.0,
    take_profit_1: float = 55000.0,
    side: str = OrderSide.BUY.value,
    status: str = SignalStatus.REJECTED_BY_FILTER.value,
    created_at: datetime | None = None,
    rejection_reason: str | None = None,
    strategy_id: str = "BULLISH_ENGULFING",
    pattern_name: str = "BULL_FLAG",
    source_collection: str = "rejected_signals",
    **extra,
) -> dict:
    """Build a raw Firestore-style signal dict for transform() input."""
    if created_at is None:
        created_at = datetime.now(timezone.utc) - timedelta(days=8)

    data = {
        "_doc_id": signal_id,
        "source_collection": source_collection,
        "signal_id": signal_id,
        "symbol": symbol,
        "asset_class": asset_class,
        "entry_price": entry_price,
        "suggested_stop": suggested_stop,
        "take_profit_1": take_profit_1,
        "side": side,
        "status": status,
        "created_at": created_at,
        "rejection_reason": rejection_reason,
        "strategy_id": strategy_id,
        "pattern_name": pattern_name,
        "valid_until": created_at + timedelta(hours=24),
    }
    data.update(extra)
    return data


def _make_bars_df(
    created_at: datetime,
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> pd.DataFrame:
    """Create a market data DataFrame with timezone-aware index."""
    dates = pd.date_range(created_at.date(), periods=len(highs), freq="D", tz="UTC")
    return pd.DataFrame({"high": highs, "low": lows, "close": closes}, index=dates)


# =====================================================================
# Extract Tests
# =====================================================================


class TestExtract:
    """Tests for dual-collection extraction."""

    def test_extract_from_both_collections(self, pipeline, mock_firestore):
        """Verify extract reads from rejected_signals AND live_signals."""
        # Rejected signal doc
        rejected_doc = MagicMock()
        rejected_doc.id = "rej_1"
        rejected_doc.to_dict.return_value = {
            "signal_id": "rej_1",
            "symbol": "BTC/USD",
            "created_at": datetime.now(timezone.utc) - timedelta(days=8),
        }

        # Live signal doc (INVALIDATED)
        live_doc = MagicMock()
        live_doc.id = "live_1"
        live_doc.to_dict.return_value = {
            "signal_id": "live_1",
            "symbol": "ETH/USD",
            "status": SignalStatus.INVALIDATED.value,
        }

        # Configure mock to return different docs per collection
        def collection_side_effect(name):
            mock_coll = MagicMock()
            if name == "rejected_signals":
                mock_coll.where.return_value.limit.return_value.stream.return_value = [
                    rejected_doc
                ]
            else:
                # live_signals — each status query returns the same doc
                mock_coll.where.return_value.limit.return_value.stream.return_value = [
                    live_doc
                ]
            return mock_coll

        mock_firestore.collection.side_effect = collection_side_effect

        raw_data = pipeline.extract()

        # Should have at least the rejected doc + live docs
        assert len(raw_data) >= 2, f"Expected at least 2 records, got {len(raw_data)}"
        # Verify _doc_id mapping (KB [2026-01-27])
        assert (
            raw_data[0]["_doc_id"] == "rej_1"
        ), f"Expected _doc_id='rej_1', got {raw_data[0]['_doc_id']!r}"
        # Verify source_collection tagging
        assert raw_data[0]["source_collection"] == "rejected_signals"

    def test_extract_empty_collections(self, pipeline, mock_firestore):
        """Extract returns empty list when no terminal signals exist."""
        mock_coll = MagicMock()
        mock_coll.where.return_value.limit.return_value.stream.return_value = []
        mock_firestore.collection.return_value = mock_coll

        raw_data = pipeline.extract()
        assert raw_data == [], f"Expected empty list, got {raw_data}"


# =====================================================================
# Transform Tests — Parametrized across all 4 status paths
# =====================================================================


class TestTransform:
    """Tests for signal → FactTheoreticalSignal transformation."""

    @pytest.mark.parametrize(
        "status, source_collection, expected_trade_type",
        [
            pytest.param(
                SignalStatus.REJECTED_BY_FILTER.value,
                "rejected_signals",
                "FILTERED",
                id="rejected_filtered",
            ),
            pytest.param(
                SignalStatus.EXPIRED.value,
                "live_signals",
                "THEORETICAL",
                id="expired_theoretical",
            ),
            pytest.param(
                SignalStatus.INVALIDATED.value,
                "live_signals",
                "THEORETICAL",
                id="invalidated_theoretical",
            ),
            pytest.param(
                SignalStatus.TP1_HIT.value,
                "live_signals",
                "EXECUTED",
                id="executed_tp1",
            ),
        ],
    )
    def test_transform_classifies_trade_type(
        self,
        pipeline,
        mock_market_provider,
        status,
        source_collection,
        expected_trade_type,
    ):
        """Verify correct trade_type classification for each status path."""
        created_at = datetime.now(timezone.utc) - timedelta(days=8)
        raw = [
            _make_raw_signal(
                signal_id=f"sig_{status}",
                status=status,
                source_collection=source_collection,
                created_at=created_at,
            )
        ]

        # Mock market data — price hits TP1
        df = _make_bars_df(
            created_at,
            highs=[51000.0, 56000.0],
            lows=[49000.0, 50000.0],
            closes=[50500.0, 54000.0],
        )
        mock_market_provider.get_daily_bars.return_value = df

        transformed = pipeline.transform(raw)

        assert len(transformed) == 1, f"Expected 1 record, got {len(transformed)}"
        assert transformed[0]["trade_type"] == expected_trade_type, (
            f"Expected trade_type={expected_trade_type!r}, "
            f"got {transformed[0]['trade_type']!r}"
        )

    def test_transform_rejected_tp_hit(self, pipeline, mock_market_provider):
        """REJECTED signal hitting TP1 gets positive theoretical P&L."""
        created_at = datetime.now(timezone.utc) - timedelta(days=8)
        raw = [
            _make_raw_signal(
                status=SignalStatus.REJECTED_BY_FILTER.value,
                created_at=created_at,
            )
        ]

        df = _make_bars_df(
            created_at,
            highs=[51000.0, 56000.0, 52000.0],
            lows=[49000.0, 50000.0, 51000.0],
            closes=[50500.0, 54000.0, 52000.0],
        )
        mock_market_provider.get_daily_bars.return_value = df

        transformed = pipeline.transform(raw)
        record = transformed[0]

        assert record["theoretical_exit_reason"] == "THEORETICAL_TP1", (
            f"Expected exit_reason='THEORETICAL_TP1', "
            f"got {record['theoretical_exit_reason']!r}"
        )
        assert record["theoretical_exit_price"] == 55000.0, (
            f"Expected exit_price=55000.0, " f"got {record['theoretical_exit_price']}"
        )
        assert (
            record["theoretical_pnl_usd"] > 0
        ), f"Expected positive P&L, got {record['theoretical_pnl_usd']}"

    def test_transform_no_market_data(self, pipeline, mock_market_provider):
        """Missing market data produces placeholder — no silent drop."""
        raw = [
            _make_raw_signal(
                signal_id="sig_no_data",
                symbol="FAKECOIN/USD",
                status=SignalStatus.EXPIRED.value,
                source_collection="live_signals",
            )
        ]
        mock_market_provider.get_daily_bars.return_value = pd.DataFrame()

        transformed = pipeline.transform(raw)

        assert (
            len(transformed) == 1
        ), f"Expected 1 record (no silent drop), got {len(transformed)}"
        assert transformed[0]["theoretical_exit_reason"] == "NO_MARKET_DATA", (
            f"Expected 'NO_MARKET_DATA', "
            f"got {transformed[0]['theoretical_exit_reason']!r}"
        )
        assert transformed[0]["theoretical_pnl_usd"] == 0.0

    def test_transform_executed_linked_trade_id(self, pipeline, mock_market_provider):
        """TP*_HIT signals set linked_trade_id as FK to fact_trades."""
        raw = [
            _make_raw_signal(
                signal_id="sig_tp1",
                status=SignalStatus.TP1_HIT.value,
                source_collection="live_signals",
            )
        ]
        mock_market_provider.get_daily_bars.return_value = pd.DataFrame()

        transformed = pipeline.transform(raw)

        assert len(transformed) == 1
        assert transformed[0]["linked_trade_id"] == "sig_tp1", (
            f"Expected linked_trade_id='sig_tp1', "
            f"got {transformed[0]['linked_trade_id']!r}"
        )

    def test_transform_executed_skips_theoretical_simulation(
        self, pipeline, mock_market_provider
    ):
        """TP*_HIT signals skip P&L simulation (real P&L in fact_trades)."""
        raw = [
            _make_raw_signal(
                signal_id="sig_tp2",
                status=SignalStatus.TP2_HIT.value,
                source_collection="live_signals",
            )
        ]
        mock_market_provider.get_daily_bars.return_value = pd.DataFrame()

        transformed = pipeline.transform(raw)

        assert transformed[0]["theoretical_exit_reason"] == (
            "EXECUTED_SEE_FACT_TRADES"
        ), (
            f"Expected 'EXECUTED_SEE_FACT_TRADES', "
            f"got {transformed[0]['theoretical_exit_reason']!r}"
        )
        assert transformed[0]["theoretical_pnl_usd"] == 0.0

    def test_transform_validation_failure(self, pipeline, mock_market_provider):
        """Validation-failed rejected signals skip market data fetch."""
        raw = [
            _make_raw_signal(
                rejection_reason="VALIDATION_FAILED: Invalid Stop",
                status=SignalStatus.REJECTED_BY_FILTER.value,
            )
        ]

        transformed = pipeline.transform(raw)

        assert len(transformed) == 1
        record = transformed[0]
        assert record["theoretical_exit_reason"] == "VALIDATION_FAILED_NO_EXECUTION", (
            f"Expected 'VALIDATION_FAILED_NO_EXECUTION', "
            f"got {record['theoretical_exit_reason']!r}"
        )
        assert record["theoretical_pnl_usd"] == 0.0
        # Market provider should NOT have been called
        mock_market_provider.get_daily_bars.assert_not_called()

    def test_transform_open_position(self, pipeline, mock_market_provider):
        """Signal that hits neither TP nor SL exits at latest close."""
        created_at = datetime.now(timezone.utc) - timedelta(days=8)
        raw = [
            _make_raw_signal(
                signal_id="sig_open",
                symbol="ETH/USD",
                entry_price=2000.0,
                suggested_stop=1900.0,
                take_profit_1=2200.0,
                status=SignalStatus.EXPIRED.value,
                source_collection="live_signals",
                created_at=created_at,
            )
        ]

        df = _make_bars_df(
            created_at,
            highs=[2050.0, 2100.0, 2080.0],
            lows=[1950.0, 1980.0, 1990.0],
            closes=[2020.0, 2090.0, 2050.0],
        )
        mock_market_provider.get_daily_bars.return_value = df

        transformed = pipeline.transform(raw)
        record = transformed[0]

        assert record["theoretical_exit_reason"] == "THEORETICAL_OPEN", (
            f"Expected 'THEORETICAL_OPEN', " f"got {record['theoretical_exit_reason']!r}"
        )
        assert record["theoretical_exit_price"] == 2050.0, (
            f"Expected exit_price=2050.0, " f"got {record['theoretical_exit_price']}"
        )

    @pytest.mark.parametrize(
        "asset_class, expected_fee_pct",
        [
            pytest.param(
                AssetClass.EQUITY.value,
                AssetClassFee.EQUITY.value,
                id="equity_zero_fee",
            ),
            pytest.param(
                AssetClass.CRYPTO.value,
                AssetClassFee.CRYPTO.value,
                id="crypto_taker_fee",
            ),
        ],
    )
    def test_transform_fees_by_asset_class(
        self,
        pipeline,
        mock_market_provider,
        asset_class,
        expected_fee_pct,
    ):
        """Verify theoretical fees are calculated based on asset class."""
        created_at = datetime.now(timezone.utc) - timedelta(days=8)
        entry_price = 100.0
        exit_price = 110.0  # TP1

        raw = [
            _make_raw_signal(
                signal_id=f"sig_fee_{asset_class}",
                symbol="AAPL" if asset_class == "EQUITY" else "BTC/USD",
                asset_class=asset_class,
                entry_price=entry_price,
                suggested_stop=90.0,
                take_profit_1=exit_price,
                created_at=created_at,
            )
        ]

        df = _make_bars_df(
            created_at,
            highs=[exit_price],
            lows=[entry_price],
            closes=[exit_price],
        )
        mock_market_provider.get_daily_bars.return_value = df

        transformed = pipeline.transform(raw)
        record = transformed[0]

        expected_fees = (
            entry_price * 1.0 * expected_fee_pct + exit_price * 1.0 * expected_fee_pct
        )
        assert record["theoretical_fees_usd"] == pytest.approx(expected_fees), (
            f"Expected fees_usd≈{expected_fees} for {asset_class}, "
            f"got {record['theoretical_fees_usd']}"
        )


# =====================================================================
# Cleanup Tests
# =====================================================================


class TestCleanup:
    """Tests for Firestore cleanup routing."""

    def test_cleanup_routes_to_correct_collection(self, pipeline, mock_firestore):
        """Verify deletes are routed to the right Firestore collection."""
        rejected = FactTheoreticalSignalFactory.build(
            doc_id="rej_1",
            signal_id="rej_1",
            status=SignalStatus.REJECTED_BY_FILTER,
            source_collection="rejected_signals",
        )
        expired = FactTheoreticalSignalFactory.build(
            doc_id="exp_1",
            signal_id="exp_1",
            status=SignalStatus.EXPIRED,
            source_collection="live_signals",
        )

        mock_batch = mock_firestore.batch.return_value
        pipeline.cleanup([rejected, expired])

        assert mock_batch.delete.called, "Expected batch.delete to be called"
        assert mock_batch.commit.called, "Expected batch.commit to be called"

    def test_cleanup_deletes_executed_signals(self, pipeline, mock_firestore):
        """TP*_HIT signals MUST be deleted from Firestore."""
        executed = FactTheoreticalSignalFactory.build(
            doc_id="tp1_1",
            signal_id="tp1_1",
            status=SignalStatus.TP1_HIT,
            source_collection="live_signals",
        )

        mock_batch = mock_firestore.batch.return_value
        pipeline.cleanup([executed])

        # batch.delete SHOULD be called for executed signals
        assert mock_batch.delete.called, "Expected batch.delete to be called"
        assert mock_batch.commit.called, "Expected batch.commit to be called"

    def test_cleanup_empty_data(self, pipeline, mock_firestore):
        """Cleanup with no data is a no-op."""
        pipeline.cleanup([])
        mock_firestore.batch.assert_not_called()

    def test_cleanup_mixed_statuses(self, pipeline, mock_firestore):
        """Mixed batch: deletes all terminal signals."""
        rejected = FactTheoreticalSignalFactory.build(
            doc_id="rej_2",
            signal_id="rej_2",
            status=SignalStatus.REJECTED_BY_FILTER,
            source_collection="rejected_signals",
        )
        tp2 = FactTheoreticalSignalFactory.build(
            doc_id="tp2_1",
            signal_id="tp2_1",
            status=SignalStatus.TP2_HIT,
            source_collection="live_signals",
        )
        invalidated = FactTheoreticalSignalFactory.build(
            doc_id="inv_1",
            signal_id="inv_1",
            status=SignalStatus.INVALIDATED,
            source_collection="live_signals",
        )

        mock_batch = mock_firestore.batch.return_value
        pipeline.cleanup([rejected, tp2, invalidated])

        # 3 deletes
        assert (
            mock_batch.delete.call_count == 3
        ), f"Expected 3 deletes, got {mock_batch.delete.call_count}"

    def test_cleanup_skips_missing_source_collection(self, pipeline, mock_firestore):
        """Cleanup skips records missing source_collection."""
        missing = FactTheoreticalSignalFactory.build(
            doc_id="mis_1",
            signal_id="mis_1",
            status=SignalStatus.REJECTED_BY_FILTER,
            source_collection=None,  # Explicitly set to None
        )

        mock_batch = mock_firestore.batch.return_value
        pipeline.cleanup([missing])

        mock_batch.delete.assert_not_called()


# =====================================================================
# Integration: run() lifecycle
# =====================================================================


class TestRunLifecycle:
    """High-level pipeline lifecycle tests."""

    def test_run_calls_schema_guardian(self, pipeline):
        """Pipeline run() invokes SchemaGuardian for validation."""
        sample = FactTheoreticalSignalFactory.build()
        pipeline.extract = MagicMock(return_value=[{"signal_id": "sig_1"}])
        pipeline.transform = MagicMock(return_value=[sample.model_dump(mode="json")])
        pipeline.cleanup = MagicMock()

        pipeline.run()

        assert pipeline.guardian.validate_schema.call_count == 1, (
            f"Expected 1 schema validation call, "
            f"got {pipeline.guardian.validate_schema.call_count}"
        )
