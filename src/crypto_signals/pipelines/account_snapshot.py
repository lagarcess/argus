"""
Account Snapshot Pipeline.

This pipeline runs daily to capture the state of the trading account (Equity, Cash)
and expanded risk metrics (Buying Power, Margin) to calculate performance metrics
(Drawdown, Calmar Ratio) based on the equity curve.

Pattern: "Extract-Transform-Load"
1. Extract: Fetch current Account and Portfolio History (1 Year) from Alpaca.
2. Transform: Calculate Peak Equity, Drawdown %, and Calmar Ratio.
3. Load: Push to BigQuery via BasePipeline (Truncate->Staging->Merge).
"""

from datetime import datetime, timezone
from typing import Any, List

from alpaca.common.exceptions import APIError
from alpaca.trading.requests import GetPortfolioHistoryRequest
from loguru import logger

from crypto_signals.config import get_trading_client
from crypto_signals.domain.schemas import AccountSnapshot
from crypto_signals.pipelines.base import BigQueryPipelineBase


class AccountSnapshotPipeline(BigQueryPipelineBase):
    """Pipeline to snapshot account state and performance metrics."""

    def __init__(self):
        """Initialize pipeline with configuration."""
        super().__init__(
            job_name="account_snapshot",
            staging_table_id=None,
            fact_table_id="",  # Placeholder
            id_column="account_id",
            partition_column="ds",
            schema_model=AccountSnapshot,
        )

        env_suffix = "" if self.settings.ENVIRONMENT == "PROD" else "_test"
        self.fact_table_id = f"{self.settings.GOOGLE_CLOUD_PROJECT}.crypto_analytics.snapshot_accounts{env_suffix}"

        # Initialize Alpaca Client
        self.alpaca = get_trading_client()

    def extract(self) -> List[Any]:
        """
        Fetch Account Snapshot and History from Alpaca.

        Returns:
            List[dict]: A single-item list containing the combined account data.
                        (Pipeline expects a list).
        """
        logger.info(f"[{self.job_name}] Fetching account data from Alpaca...")

        try:
            # 1. Get Current Account State (Equity, Cash, ID)
            account = self.alpaca.get_account()

            # 2. Get Portfolio History (1 Year) to calculate Peak Equity
            # We need this for Drawdown calculation (Peak - Current / Peak)
            history_req = GetPortfolioHistoryRequest(
                period="1A",
                timeframe="1D",
                date_end=None,
                extended_hours=False,
            )
            history = self.alpaca.get_portfolio_history(history_req)

            # Combine into a single raw payload
            raw_data = {"account": account, "history": history}

            return [raw_data]

        except APIError as e:
            logger.error(
                f"[{self.job_name}] Alpaca API Error.",
                extra={"error": str(e)},
            )
            raise

    def transform(self, raw_data: List[Any]) -> List[dict]:
        """
        Calculate metrics and shape data for BigQuery.

        Includes defensive math (Guardrails) for new or empty accounts.

        Args:
            raw_data: List containing the single raw_data dict from extract.

        Returns:
            List[dict]: Transformed data matching StagingAccount schema.
        """
        transformed = []

        # Helper for safe parsing
        def _parse_float(value: Any) -> float:
            if value is None:
                return 0.0
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0

        def _parse_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() == "true"
            return False

        def _parse_str(value: Any, default: str) -> str:
            if value is None:
                return default
            if isinstance(value, str):
                return value
            return str(value)

        for item in raw_data:
            account = item["account"]
            history = item["history"]

            # -----------------------------------------------------------------
            # 1. Parse Basic Account Info
            # -----------------------------------------------------------------
            account_id = str(account.id)
            current_equity = _parse_float(account.equity)
            cash = _parse_float(account.cash)

            # -----------------------------------------------------------------
            # 2. Calculate Drawdown (Current)
            # -----------------------------------------------------------------
            # history.equity is a list of float values
            equity_curve = history.equity or []

            # Peak Equity should include current equity
            all_equities = equity_curve + [current_equity]
            peak_equity = max(all_equities) if all_equities else current_equity

            # Guardrail: If peak <= 0, we can't have a drawdown (div zero)
            if peak_equity > 0:
                # Math: (Peak - Current) / Peak
                drawdown_pct = (peak_equity - current_equity) / peak_equity * 100.0
            else:
                drawdown_pct = 0.0

            # -----------------------------------------------------------------
            # 3. Calculate Calmar Ratio
            # Formula: Annualized Return / Max Drawdown
            # Guardrails:
            #   1. History < 30 days -> 0.0 (Too specific/unstable)
            #   2. Start Equity <= 0 -> 0.0 (Div zero)
            #   3. Max Drawdown == 0 -> 0.0 (Infinite ratio)
            # -----------------------------------------------------------------
            calmar_ratio = 0.0

            # Check 1: History Length
            # Alpaca history returns only business days, so 30 days history is roughly
            # 20-22 biz days? User specified "If history length < 30 days".
            # We'll stick to literal length of the list (days of data).
            if len(equity_curve) >= 30:
                # Check 2: Start Equity
                start_equity = equity_curve[0]
                if start_equity > 0:
                    # Calculate Return

                    # Annualize Return
                    # ((1 + TotalReturn) ^ (365 / Days)) - 1
                    # Use len(equity_curve) as proxy for trading days ~ 252/year
                    days = len(equity_curve)
                    if days > 0:
                        annualized_return = (
                            (current_equity / start_equity) ** (252 / days)
                        ) - 1
                    else:
                        annualized_return = 0.0

                    # Calculate Max Drawdown (The denominator)
                    # We need the max drawdown seen throughout the period
                    running_peak = 0.0
                    max_dd = 0.0

                    for eq in equity_curve:
                        if eq > running_peak:
                            running_peak = eq

                        if running_peak > 0:
                            dd = (running_peak - eq) / running_peak
                            if dd > max_dd:
                                max_dd = dd

                    # Check current DD
                    current_dd = (
                        (peak_equity - current_equity) / peak_equity
                        if peak_equity > 0
                        else 0
                    )
                    if current_dd > max_dd:
                        max_dd = current_dd

                    # Debug Log
                    logger.info(
                        f"CALMAR DEBUG: Start={start_equity} End={current_equity} "
                        f"Days={len(equity_curve)} AnnRet={annualized_return} "
                        f"MaxDD={max_dd}"
                    )

                    # Check 3: Max Drawdown
                    if max_dd > 0:
                        # Calmar = Annualized Return / Max Drawdown
                        # Note: Return is 0.20 (20%), MaxDD is 0.10 (10%) -> 2.0
                        calmar_ratio = annualized_return / max_dd

            # -----------------------------------------------------------------
            # 4. Construct Output
            # -----------------------------------------------------------------
            snapshot_date = datetime.now(timezone.utc).date()

            record = AccountSnapshot(
                ds=snapshot_date,
                account_id=account_id,
                equity=round(current_equity, 2),
                cash=round(cash, 2),
                calmar_ratio=round(calmar_ratio, 2),
                drawdown_pct=round(drawdown_pct, 4),
                # === NEW FIELDS (Issue 116) ===
                buying_power=_parse_float(getattr(account, "buying_power", 0.0)),
                regt_buying_power=_parse_float(
                    getattr(account, "regt_buying_power", 0.0)
                ),
                daytrading_buying_power=_parse_float(
                    getattr(account, "daytrading_buying_power", 0.0)
                ),
                crypto_buying_power=_parse_float(
                    getattr(account, "non_marginable_buying_power", 0.0)
                ),
                initial_margin=_parse_float(getattr(account, "initial_margin", 0.0)),
                maintenance_margin=_parse_float(
                    getattr(account, "maintenance_margin", 0.0)
                ),
                last_equity=_parse_float(getattr(account, "last_equity", 0.0)),
                long_market_value=_parse_float(
                    getattr(account, "long_market_value", 0.0)
                ),
                short_market_value=_parse_float(
                    getattr(account, "short_market_value", 0.0)
                ),
                currency=_parse_str(getattr(account, "currency", "USD"), "USD"),
                status=_parse_str(getattr(account, "status", "ACTIVE"), "ACTIVE"),
                pattern_day_trader=_parse_bool(
                    getattr(account, "pattern_day_trader", False)
                ),
                daytrade_count=int(getattr(account, "daytrade_count", 0) or 0),
                account_blocked=_parse_bool(getattr(account, "account_blocked", False)),
                trade_suspended_by_user=_parse_bool(
                    getattr(account, "trade_suspended_by_user", False)
                ),
                trading_blocked=_parse_bool(getattr(account, "trading_blocked", False)),
                transfers_blocked=_parse_bool(
                    getattr(account, "transfers_blocked", False)
                ),
                multiplier=_parse_float(getattr(account, "multiplier", 1.0)),
                sma=_parse_float(getattr(account, "sma", 0.0)),
            )

            transformed.append(record.model_dump(mode="json"))

        return transformed

    def cleanup(self, data: List[Any]) -> None:
        """No cleanup required for Account Snapshot (Read-Only API)."""
