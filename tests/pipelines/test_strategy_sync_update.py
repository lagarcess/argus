import json
from unittest.mock import MagicMock, patch

import pytest
from crypto_signals.domain.schemas import AssetClass, StrategyConfig
from crypto_signals.pipelines.strategy_sync import StrategySyncPipeline


class TestStrategySyncUpdate:
    """Tests for StrategySyncPipeline updates including new fields."""

    @pytest.fixture
    def mock_repo(self):
        with patch("crypto_signals.pipelines.strategy_sync.StrategyRepository") as mock:
            yield mock.return_value

    @pytest.fixture
    def mock_bq_client(self):
        with patch("google.cloud.bigquery.Client") as mock:
            yield mock.return_value

    @pytest.fixture
    def pipeline(self, mock_repo, mock_bq_client):
        # We need to mock BigQueryPipelineBase.__init__ because it creates a BQ client
        with patch(
            "crypto_signals.pipelines.base.bigquery.Client", return_value=mock_bq_client
        ):
            pipeline = StrategySyncPipeline()
            pipeline.repository = mock_repo
            pipeline.bq_client = mock_bq_client
            # Mock _check_table_exists to return True
            pipeline._check_table_exists = MagicMock(return_value=True)
            return pipeline

    def test_extract_detects_changes_in_new_fields(self, pipeline, mock_repo):
        """Verify that changes to confluence_config trigger an update."""
        # 1. Setup Firestore Mock
        strategy = StrategyConfig(
            strategy_id="strat_1",
            active=True,
            timeframe="1D",
            asset_class=AssetClass.CRYPTO,
            assets=["BTC/USD"],
            risk_params={"stop_loss_pct": 0.02},
            confluence_config={"rsi_period": 14},  # New field value
            pattern_overrides={},
        )
        mock_repo.get_all_strategies.return_value = [strategy]

        # 2. Setup BigQuery State Mock (Simulate OLD state without confluence config)
        # Calculate hash of old config
        old_config_data = strategy.model_dump()
        old_config_data["confluence_config"] = {}  # Difference!

        # We need to manually calculate the hash using the pipeline's logic
        # but the pipeline's _calculate_hash method uses RELEVANT_CONFIG_KEYS
        # which now includes confluence_config.

        # To simulate a change, we pretend BQ has a different hash.
        # Any different hash will trigger an update.
        pipeline._get_bq_current_state = MagicMock(
            return_value={"strat_1": "old_hash_123"}
        )

        # 3. Run Extract
        staging_records = pipeline.extract()

        # 4. Verify
        assert len(staging_records) == 1
        record = staging_records[0]
        assert record["strategy_id"] == "strat_1"

        # Verify new fields are present and JSON serialized
        assert "confluence_config" in record
        # ConfluenceConfig model includes defaults on serialization
        from crypto_signals.domain.schemas import ConfluenceConfig

        expected_config = ConfluenceConfig().model_dump()
        assert json.loads(record["confluence_config"]) == expected_config

        assert "pattern_overrides" in record
        assert json.loads(record["pattern_overrides"]) == {}

    def test_extract_hash_calculation_includes_new_fields(self, pipeline):
        """Verify hash calculation differs when new fields change."""

        config1 = {
            "active": True,
            "timeframe": "1D",
            "asset_class": "CRYPTO",
            "assets": ["BTC/USD"],
            "risk_params": {},
            "confluence_config": {"rsi": 14},
            "pattern_overrides": {},
        }

        config2 = {
            "active": True,
            "timeframe": "1D",
            "asset_class": "CRYPTO",
            "assets": ["BTC/USD"],
            "risk_params": {},
            "confluence_config": {"rsi": 21},  # Changed!
            "pattern_overrides": {},
        }

        hash1 = pipeline._calculate_hash(config1)
        hash2 = pipeline._calculate_hash(config2)

        assert hash1 != hash2, "Hash should change when confluence_config changes"

    def test_extract_populates_json_fields_correctly(self, pipeline, mock_repo):
        """Verify JSON fields are correctly dumped in staging record."""
        # 1. Setup Firestore Mock
        strategy = StrategyConfig(
            strategy_id="strat_json",
            active=True,
            timeframe="1D",
            asset_class=AssetClass.CRYPTO,
            assets=["BTC/USD"],
            risk_params={"sl": 0.1},
            confluence_config={"rsi": 14},
            pattern_overrides={"engulfing": {"p": 1}},
        )
        mock_repo.get_all_strategies.return_value = [strategy]

        # Simulate BQ state empty (new strategy)
        pipeline._get_bq_current_state = MagicMock(return_value={})

        # 2. Extract
        staging_records = pipeline.extract()

        # 3. Verify
        assert len(staging_records) == 1
        record = staging_records[0]

        assert record["risk_params"] == '{"sl": 0.1}'
        # ConfluenceConfig model serializes with sorted keys and includes defaults
        # Since "rsi" is not a known field, it's stored via extra="allow"
        from crypto_signals.domain.schemas import ConfluenceConfig

        expected_config = ConfluenceConfig().model_dump()
        expected_config["rsi"] = 14
        assert json.loads(record["confluence_config"]) == expected_config
        assert record["pattern_overrides"] == '{"engulfing": {"p": 1}}'
