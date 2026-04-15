"""
Persistence Service for Argus.

Handles saving and retrieving strategies and simulation results
from the Supabase PostgreSQL database.
"""

from typing import Any, Dict, List, Optional, cast

from loguru import logger

from argus.api.schemas import SimulationLogEntry
from argus.config import get_settings
from argus.engine import EngineBacktestResults
from supabase import Client, create_client


class PersistenceService:
    def __init__(self):
        settings = get_settings()
        supabase_url = settings.SUPABASE_URL
        supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY

        if supabase_url and supabase_key:
            try:
                self.client: Optional[Client] = create_client(supabase_url, supabase_key)
            except Exception as e:
                logger.error(
                    "Failed to initialize PersistenceService Supabase client. "
                    f"url={supabase_url!r} error={e}"
                )
                self.client = None
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
                "symbols": strategy_data.get("symbols", []),
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
        symbols: List[str],
        timeframe: str,
        result: EngineBacktestResults,
        config_snapshot: Dict[str, Any],
        simulation_id: Optional[str] = None,
    ) -> Optional[str]:
        """Saves a simulation result and returns its UUID."""
        if not self.client:
            return None

        try:
            # Prepare summary from flattened results
            summary_fields = {
                "total_return_pct",
                "win_rate",
                "sharpe_ratio",
                "sortino_ratio",
                "calmar_ratio",
                "profit_factor",
                "expectancy",
                "max_drawdown_pct",
            }
            summary_data = {
                k: v for k, v in result.model_dump().items() if k in summary_fields
            }

            data: Dict[str, Any] = {
                "user_id": user_id,
                "strategy_id": strategy_id,
                "symbols": symbols,
                "timeframe": timeframe,
                "config_snapshot": config_snapshot,
                "summary": summary_data,
                "reality_gap_metrics": result.reality_gap_metrics,
                "full_result": {
                    "equity_curve": result.equity_curve,
                    "trades": result.trades,
                    "pattern_breakdown": result.pattern_breakdown,
                },
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
                .select("*")
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
                .select("id, symbols, timeframe, created_at, summary, strategies(name)")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )

            summaries: List[Dict[str, Any]] = []
            for row in res.data:
                strategy_data: Any = cast(Dict[str, Any], row).get("strategies", {})
                if isinstance(strategy_data, list) and len(strategy_data) > 0:
                    strategy_name = strategy_data[0].get("name", "Unknown Strategy")
                elif isinstance(strategy_data, dict):
                    strategy_name = cast(Dict[str, Any], strategy_data).get(
                        "name", "Unknown Strategy"
                    )
                else:
                    strategy_name = "Unknown Strategy"

                entry_data = {
                    "id": cast(Dict[str, Any], row).get("id"),
                    "strategy_name": strategy_name,
                    "symbols": cast(Dict[str, Any], row).get("symbols") or [],
                    "timeframe": cast(Dict[str, Any], row).get("timeframe"),
                    "status": "completed",
                    "created_at": cast(Dict[str, Any], row).get("created_at"),
                }

                # Mix in the summary metrics
                metrics = cast(Dict[str, Any], row).get("summary", {})
                entry_data.update(metrics)

                # Validate against schema and dump for response
                summary = SimulationLogEntry.model_validate(entry_data).model_dump()
                summaries.append(summary)

            return summaries, total

        except Exception as e:
            logger.error(f"Failed to fetch user simulations: {e}")
            return [], 0
