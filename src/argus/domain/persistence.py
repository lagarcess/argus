"""
Persistence Service for Argus.

Handles saving and retrieving strategies and simulation results
from the Supabase PostgreSQL database.
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from argus.config import get_settings
from argus.engine import BacktestResult, StrategyConfig
from supabase import Client, create_client


class PersistenceService:
    def __init__(self):
        settings = get_settings()
        supabase_url = settings.SUPABASE_URL
        supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY

        if supabase_url and supabase_key:
            self.client: Optional[Client] = create_client(supabase_url, supabase_key)
        else:
            logger.warning("Supabase credentials missing. Persistence Service disabled.")
            self.client = None

    def save_strategy(
        self, user_id: str, name: str, config: StrategyConfig
    ) -> Optional[str]:
        """Saves a strategy and returns its UUID."""
        if not self.client:
            return None

        try:
            res = (
                self.client.table("strategies")
                .insert(
                    {
                        "user_id": user_id,
                        "name": name,
                        "config": config.model_dump(mode="json"),
                    }
                )
                .execute()
            )
            if res.data:
                return str(res.data[0]["id"])
            return None
        except Exception as e:
            logger.error(f"Failed to save strategy: {e}")
            return None

    def save_simulation(
        self,
        user_id: str,
        strategy_id: str,
        symbol: str,
        timeframe: str,
        result: BacktestResult,
        simulation_id: Optional[str] = None,
    ) -> Optional[str]:
        """Saves a simulation result and returns its UUID."""
        if not self.client:
            return None

        try:
            data = {
                "user_id": user_id,
                "strategy_id": strategy_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "result": result.model_dump(mode="json"),
            }
            if simulation_id:
                data["id"] = simulation_id

            res = self.client.table("simulations").insert(data).execute()
            if res.data:
                return str(res.data[0]["id"])
            return None
        except Exception as e:
            logger.error(f"Failed to save simulation: {e}")
            return None

    def get_simulation(self, simulation_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a specific simulation result by ID."""
        if not self.client:
            return None

        try:
            res = (
                self.client.table("simulations")
                .select("*, strategies(name, config)")
                .eq("id", simulation_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            return res.data
        except Exception as e:
            logger.error(f"Failed to fetch simulation {simulation_id}: {e}")
            return None

    def get_user_simulations(
        self, user_id: str, limit: int = 10, offset: int = 0
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Fetches a paginated list of summarized simulations for a user.
        Joins with the strategies table to get the strategy name.
        """
        if not self.client:
            return [], 0

        try:
            # Get total count
            count_res = (
                self.client.table("simulations")
                .select("id", count="exact")  # type: ignore
                .eq("user_id", user_id)
                .execute()
            )
            total = count_res.count if count_res.count else 0

            # Fetch paginated data joined with strategy name
            res = (
                self.client.table("simulations")
                .select("id, symbol, timeframe, created_at, result, strategies(name)")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

            summaries = []
            for row in res.data:
                # Safely extract metrics from the stored JSONB
                result_data: Any = row.get("result", {})
                metrics = result_data.get("metrics", {})

                strategy_data: Any = row.get("strategies", {})
                # Some Supabase setups return objects, some arrays for joins depending on relation type
                if isinstance(strategy_data, list) and len(strategy_data) > 0:
                    strategy_name = strategy_data[0].get("name", "Unknown Strategy")
                elif isinstance(strategy_data, dict):
                    strategy_name = strategy_data.get("name", "Unknown Strategy")
                else:
                    strategy_name = "Unknown Strategy"

                summary = {
                    "id": row.get("id"),
                    "strategy_name": strategy_name,
                    "symbols": [row.get("symbol")] if row.get("symbol") else [],
                    "timeframe": row.get("timeframe"),
                    "status": "completed",
                    "total_return_pct": metrics.get("total_return_pct", 0.0),
                    "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                    "win_rate_pct": metrics.get("win_rate_pct", 0.0),
                    "max_drawdown_pct": metrics.get("max_drawdown_pct", 0.0),
                    "total_trades": metrics.get("total_trades", 0),
                    "alpha": metrics.get("alpha", 0.0),
                    "beta": metrics.get("beta", 0.0),
                    "calmar_ratio": metrics.get("calmar_ratio", 0.0),
                    "avg_trade_duration": metrics.get("avg_trade_duration", "0m"),
                    "created_at": row.get("created_at"),
                }
                summaries.append(summary)

            return summaries, total

        except Exception as e:
            logger.error(f"Failed to fetch user simulations: {e}")
            return [], 0
