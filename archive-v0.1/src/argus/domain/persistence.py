"""
Persistence Service for Argus.

Handles saving and retrieving strategies and simulation results
from the Supabase PostgreSQL database.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from loguru import logger

from argus.config import get_settings
from argus.engine import EngineBacktestResults
from supabase import Client, create_client


class PersistenceError(RuntimeError):
    """Raised when persistence operations fail in strict mode."""


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
        *,
        strict: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Saves a strategy using the new schema and returns the full record."""
        if not self.client:
            if strict:
                raise PersistenceError("Supabase persistence client is not configured.")
            return None

        try:
            indicators_config = dict(strategy_data.get("indicators_config", {}) or {})
            # Keep execution fields mirrored inside indicators_config until a dedicated
            # execution_config column is introduced; this preserves compatibility for
            # existing reads that hydrate execution settings from indicators_config.
            for field in (
                "capital",
                "trade_direction",
                "participation_rate",
                "execution_priority",
                "va_sensitivity",
                "slippage_model",
            ):
                if strategy_data.get(field) is not None:
                    indicators_config[field] = strategy_data[field]

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
                "indicators_config": indicators_config,
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
            if strict:
                raise PersistenceError("Failed to save strategy.") from e
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
        self,
        user_id: str,
        limit: int = 10,
        cursor: Optional[str] = None,
        *,
        strict: bool = False,
    ) -> Optional[tuple[List[Dict[str, Any]], Optional[str]]]:
        """Fetches a paginated list of strategies for a user using cursor pagination."""
        import base64

        if not self.client:
            if strict:
                raise PersistenceError("Supabase persistence client is not configured.")
            return None

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
            if strict:
                raise PersistenceError("Failed to list strategies.") from e
            return None

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
                "symbol": symbols[0] if symbols else "UNKNOWN",
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

    def save_telemetry_event(
        self,
        user_id: str,
        event: str,
        event_ts: datetime,
        properties: Dict[str, Any],
        *,
        strict: bool = False,
    ) -> bool:
        """Persist a telemetry funnel event for private-beta observability."""
        if not self.client:
            if strict:
                raise PersistenceError("Supabase persistence client is not configured.")
            return False

        try:
            data = {
                "user_id": user_id,
                "event": event,
                "event_ts": event_ts.isoformat(),
                "properties": properties,
            }
            self.client.table("telemetry_events").insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to save telemetry event: {e}")
            if strict:
                raise PersistenceError("Failed to save telemetry event.") from e
            return False

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
        self,
        user_id: str,
        limit: int = 10,
        cursor: Optional[str] = None,
        *,
        strict: bool = False,
    ) -> Optional[tuple[List[Dict[str, Any]], int, Optional[str]]]:
        """
        Fetches a paginated list of summarized simulations for a user.
        Joins with the strategies table to get the strategy name.
        """
        import base64
        import json

        if not self.client:
            if strict:
                raise PersistenceError("Supabase persistence client is not configured.")
            return None

        try:
            # Get total count
            count_res = (
                self.client.table("simulations")
                .select("id", count="exact")  # type: ignore
                .eq("user_id", user_id)
                .execute()
            )
            total = count_res.count if count_res.count else 0

            def _execute_simulations_query(select_clause: str) -> Any:
                query = (
                    self.client.table("simulations")
                    .select(select_clause)
                    .eq("user_id", user_id)
                    .order("created_at", desc=True)
                    .order("id", desc=True)
                    .limit(limit)
                )

                if cursor:
                    try:
                        decoded = base64.urlsafe_b64decode(cursor).decode("utf-8")
                        cursor_data = json.loads(decoded)
                        if isinstance(cursor_data, dict):
                            timestamp_str = cursor_data.get("created_at")
                            id_str = cursor_data.get("id")
                            if timestamp_str and id_str:
                                query = query.or_(
                                    f"created_at.lt.{timestamp_str},and(created_at.eq.{timestamp_str},id.lt.{id_str})"
                                )
                        elif "+" in decoded:
                            # Backward compatibility for older cursors.
                            timestamp_str, id_str = decoded.split("+", 1)
                            query = query.or_(
                                f"created_at.lt.{timestamp_str},and(created_at.eq.{timestamp_str},id.lt.{id_str})"
                            )
                    except Exception as e:
                        logger.warning(f"Invalid cursor format: {cursor}, {e}")

                return query.execute()

            uses_symbols_array = True
            try:
                res = _execute_simulations_query(
                    "id, symbols, timeframe, created_at, summary, reality_gap_metrics, strategies(name)"
                )
            except Exception as e:
                # Backward compatibility for databases still on legacy `symbol` column.
                if "symbols" not in str(e).lower():
                    raise
                uses_symbols_array = False
                res = _execute_simulations_query(
                    "id, symbol, timeframe, created_at, summary, reality_gap_metrics, strategies(name)"
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
                    "symbols": (
                        cast(Dict[str, Any], row).get("symbols") or []
                        if uses_symbols_array
                        else (
                            [cast(Dict[str, Any], row).get("symbol")]
                            if cast(Dict[str, Any], row).get("symbol")
                            else []
                        )
                    ),
                    "timeframe": cast(Dict[str, Any], row).get("timeframe"),
                    "status": "completed",
                    "created_at": cast(Dict[str, Any], row).get("created_at"),
                }

                # Mix in the summary metrics
                metrics = cast(Dict[str, Any], row).get("summary", {})
                if isinstance(metrics, str):
                    import json

                    try:
                        metrics = json.loads(metrics)
                    except Exception:
                        metrics = {}
                entry_data.update(metrics)

                # fidelity_score from reality_gap_metrics
                reality_gap_metrics = (
                    cast(Dict[str, Any], row).get("reality_gap_metrics", {}) or {}
                )
                if isinstance(reality_gap_metrics, str):
                    import json

                    try:
                        reality_gap_metrics = json.loads(reality_gap_metrics)
                    except Exception:
                        reality_gap_metrics = {}

                fidelity_score = reality_gap_metrics.get("fidelity_score", 1.0)
                entry_data["fidelity_score"] = fidelity_score

                # The schema might need update before this, but we'll return entry_data first then validate in main.py or update schema now.
                # Let's bypass model_validate here so we don't crash if schema isn't updated yet. We'll return entry_data dictionary.
                summaries.append(entry_data)

            next_cursor = None
            if len(res.data) == limit:
                last_row: Any = res.data[-1]
                last_ts = cast(Dict[str, Any], last_row).get("created_at")
                last_id = cast(Dict[str, Any], last_row).get("id")
                if last_ts and last_id:
                    cursor_payload = json.dumps(
                        {"created_at": last_ts, "id": last_id}, separators=(",", ":")
                    )
                    next_cursor = base64.urlsafe_b64encode(
                        cursor_payload.encode("utf-8")
                    ).decode("utf-8")

            return summaries, total, next_cursor

        except Exception as e:
            logger.error(f"Failed to fetch user simulations: {e}")
            if strict:
                raise PersistenceError("Failed to fetch simulation history.") from e
            return None
