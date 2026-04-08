"""
Persistence Service for Argus.

Handles saving and retrieving strategies and simulation results
from the Supabase PostgreSQL database.
"""

from typing import Any, Dict, List, Optional, cast

from loguru import logger

from argus.config import get_settings
from argus.engine import BacktestResult
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
        self,
        user_id: str,
        strategy_data: Dict[str, Any],
        strategy_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Saves a strategy using the new schema and returns the full record."""
        if not self.client:
            return None

        try:
            data: Dict[str, Any] = {
                "user_id": user_id,
                "name": strategy_data.get("name"),
                "symbol": strategy_data.get("symbol"),
                "timeframe": strategy_data.get("timeframe"),
                "start_date": strategy_data["start_date"].isoformat()
                if strategy_data.get("start_date")
                else None,
                "end_date": strategy_data["end_date"].isoformat()
                if strategy_data.get("end_date")
                else None,
                "entry_criteria": strategy_data.get("entry_criteria", []),
                "exit_criteria": strategy_data.get("exit_criteria", {}),
                "indicators_config": strategy_data.get("indicators_config", {}),
                "patterns": strategy_data.get("patterns", []),
                "executed_at": strategy_data.get("executed_at"),
            }
            if strategy_id:
                data["id"] = strategy_id

            res = (
                self.client.table("strategies")
                .upsert(data)  # type: ignore
                .execute()
            )
            if res.data:
                return cast(Dict[str, Any], res.data[0])
            return None
        except Exception as e:
            logger.error(f"Failed to save strategy: {e}")
            return None

    def get_strategy(self, strategy_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a specific strategy by ID."""
        if not self.client:
            return None
        try:
            res = (
                self.client.table("strategies")
                .select("*")
                .eq("id", strategy_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            return cast(Dict[str, Any], res.data)
        except Exception as e:
            logger.error(f"Failed to fetch strategy {strategy_id}: {e}")
            return None

    def delete_strategy(self, strategy_id: str, user_id: str) -> bool:
        """Deletes a strategy if it belongs to the user and hasn't been executed."""
        if not self.client:
            return False
        try:
            res = (
                self.client.table("strategies")
                .delete()
                .eq("id", strategy_id)
                .eq("user_id", user_id)
                .is_("executed_at", "null")
                .execute()
            )
            return len(res.data) > 0
        except Exception as e:
            logger.error(f"Failed to delete strategy {strategy_id}: {e}")
            return False

    def list_strategies(
        self, user_id: str, limit: int = 10, cursor: Optional[str] = None
    ) -> tuple[List[Dict[str, Any]], Optional[str]]:
        """Fetches a paginated list of strategies for a user using cursor pagination."""
        import base64

        if not self.client:
            return [], None

        try:
            query = (
                self.client.table("strategies")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .order("id", desc=True)
                .limit(limit)
            )

            if cursor:
                try:
                    decoded = base64.b64decode(cursor).decode("utf-8")
                    # format: timestamp_iso+id
                    if "+" in decoded:
                        timestamp_str, id_str = decoded.split("+", 1)
                        # Use complex filter for tie-breaking
                        query = query.or_(
                            f"created_at.lt.{timestamp_str},and(created_at.eq.{timestamp_str},id.lt.{id_str})"
                        )
                except Exception as e:
                    logger.warning(f"Invalid cursor format: {cursor}, {e}")

            res = query.execute()
            strategies = res.data

            next_cursor = None
            if len(strategies) == limit:
                last: Any = strategies[-1]
                last_ts = cast(Dict[str, Any], last).get("created_at")
                last_id = cast(Dict[str, Any], last).get("id")
                if last_ts and last_id:
                    cursor_str = f"{last_ts}+{last_id}"
                    next_cursor = base64.b64encode(cursor_str.encode("utf-8")).decode(
                        "utf-8"
                    )

            return cast(List[Dict[str, Any]], strategies), next_cursor
        except Exception as e:
            logger.error(f"Failed to list strategies: {e}")
            return [], None

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
            data: Dict[str, Any] = {
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
                return str(cast(Dict[str, Any], res.data[0])["id"])
            return None
        except Exception as e:
            logger.error(f"Failed to save simulation: {e}")
            return None

    def get_simulation(
        self, simulation_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
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
            return cast(Dict[str, Any], res.data)
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

            summaries: List[Dict[str, Any]] = []
            for row in res.data:
                # Safely extract metrics from the stored JSONB
                result_data: Any = cast(Dict[str, Any], row).get("result", {})
                metrics = cast(Dict[str, Any], result_data).get("metrics", {})

                strategy_data: Any = cast(Dict[str, Any], row).get("strategies", {})
                # Some Supabase setups return objects, some arrays for joins depending on relation type
                if isinstance(strategy_data, list) and len(strategy_data) > 0:
                    strategy_name = strategy_data[0].get("name", "Unknown Strategy")
                elif isinstance(strategy_data, dict):
                    strategy_name = cast(Dict[str, Any], strategy_data).get(
                        "name", "Unknown Strategy"
                    )
                else:
                    strategy_name = "Unknown Strategy"

                summary = {
                    "id": cast(Dict[str, Any], row).get("id"),
                    "strategy_name": strategy_name,
                    "symbols": [cast(Dict[str, Any], row).get("symbol")]
                    if cast(Dict[str, Any], row).get("symbol")
                    else [],
                    "timeframe": cast(Dict[str, Any], row).get("timeframe"),
                    "status": "completed",
                    "total_return_pct": cast(Dict[str, Any], metrics).get(
                        "total_return_pct", 0.0
                    ),
                    "sharpe_ratio": cast(Dict[str, Any], metrics).get(
                        "sharpe_ratio", 0.0
                    ),
                    "win_rate_pct": cast(Dict[str, Any], metrics).get(
                        "win_rate_pct", 0.0
                    ),
                    "max_drawdown_pct": cast(Dict[str, Any], metrics).get(
                        "max_drawdown_pct", 0.0
                    ),
                    "total_trades": cast(Dict[str, Any], metrics).get("total_trades", 0),
                    "alpha": cast(Dict[str, Any], metrics).get("alpha", 0.0),
                    "beta": cast(Dict[str, Any], metrics).get("beta", 0.0),
                    "calmar_ratio": cast(Dict[str, Any], metrics).get(
                        "calmar_ratio", 0.0
                    ),
                    "avg_trade_duration": cast(Dict[str, Any], metrics).get(
                        "avg_trade_duration", "0m"
                    ),
                    "created_at": cast(Dict[str, Any], row).get("created_at"),
                }
                summaries.append(summary)

            return summaries, total

        except Exception as e:
            logger.error(f"Failed to fetch user simulations: {e}")
            return [], 0
