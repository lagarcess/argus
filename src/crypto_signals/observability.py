"""
Observability Module with Rich Integration.

This module provides structured logging, metrics collection, and terminal UI
capabilities using Rich for beautiful, readable output. It transforms the
terminal from a "wall of text" into a real-time dashboard.

Key Features:
- Color-coded log levels via RichHandler
- Rich tracebacks with local variable inspection
- Progress bars for portfolio processing
- Structured tables for execution summaries
"""

import threading
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from loguru import logger
from rich import traceback as rich_traceback
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.theme import Theme

# =============================================================================
# RICH CONFIGURATION
# =============================================================================

# Custom theme for consistent branding
SENTINEL_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "bold red",
        "critical": "bold white on red",
        "success": "bold green",
        "symbol": "bold magenta",
        "signal": "bold cyan",
    }
)

# Global console instance for UI elements
console = Console(theme=SENTINEL_THEME)

# Install rich tracebacks globally (show_locals=True for debugging "God Mode")
rich_traceback.install(console=console, show_locals=True, width=120)


def configure_logging(level: str = "INFO", testing: bool = False) -> None:
    """
    Configure loguru to use Rich for beautiful terminal output.

    This function should be called at application startup to enable
    color-coded logs with automatic column sizing.

    Args:
        level: Minimum log level to display (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        testing: If True, do not remove existing handlers to allow pytest capture.
    """
    import logging

    # In testing, we want pytest's log capture to work.
    if not testing:
        logger.remove()
        # Add Rich-formatted handler for non-testing environments
        logger.add(
            _rich_sink,
            format="{message}",
            level=level,
            colorize=False,  # Rich handles colors
        )
    else:
        # For testing, add a handler that pytest can capture.
        logger.add(logging.StreamHandler(), format="{message}", level=level)


def _rich_sink(message) -> None:
    """
    Custom sink function for loguru that formats output through Rich.

    This provides color-coded log levels and automatic column sizing.
    """
    record = message.record
    level = record["level"].name

    # Map loguru levels to Rich styles
    level_styles = {
        "TRACE": "dim",
        "DEBUG": "dim cyan",
        "INFO": "green",
        "SUCCESS": "bold green",
        "WARNING": "yellow",
        "ERROR": "bold red",
        "CRITICAL": "bold white on red",
    }

    style = level_styles.get(level, "")
    timestamp = record["time"].strftime("%Y-%m-%d %H:%M:%S")

    # Format: timestamp | level | message
    console.print(
        f"[dim]{timestamp}[/dim] | [{style}]{level:8}[/{style}] | {record['message']}"
    )


# =============================================================================
# GCP CLOUD LOGGING
# =============================================================================

# Map Loguru levels to GCP Cloud Logging severities
# GCP does not have SUCCESS level, so we map it to INFO
LOGURU_TO_GCP_SEVERITY = {
    "TRACE": "DEBUG",
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "SUCCESS": "INFO",  # GCP has no SUCCESS, use INFO
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}


def _serialize_for_json(value: Any) -> Any:
    """
    Safely serialize a value for JSON logging payload.

    Handles common non-JSON-serializable types like datetime, Decimal,
    Enum, and custom objects by converting them to strings.

    Args:
        value: Any value that might be in the extra context

    Returns:
        A JSON-serializable version of the value
    """
    from datetime import date, datetime
    from decimal import Decimal
    from enum import Enum

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, Enum):
        return value.value
    elif isinstance(value, dict):
        return {k: _serialize_for_json(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [_serialize_for_json(item) for item in value]
    else:
        # Fallback: convert to string representation
        return str(value)


def _sanitize_extra_context(extra: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize extra context dictionary for safe JSON serialization.

    Args:
        extra: The extra context dict from a Loguru record

    Returns:
        A sanitized dict with all values JSON-serializable
    """
    if not extra:
        return {}
    return {key: _serialize_for_json(value) for key, value in extra.items()}


def setup_gcp_logging(log_name: str = "crypto-sentinel") -> bool:
    """
    Configure Google Cloud Logging sink for production environments.

    Adds a structured JSON sink that sends logs to GCP Cloud Logging
    while preserving the Rich terminal output for local development.

    When running on GCP (Cloud Run or GKE), Google's logging agent
    automatically parses JSON logs into jsonPayload, making every
    field (symbol, qty, pnl_usd, etc.) searchable in Logs Explorer.

    **Error Handling:**
    - If GCP client initialization fails (missing credentials, network issues),
      this function logs a warning and returns False. The application will
      continue with only Rich terminal logging.
    - If individual log writes fail, errors are silently ignored to prevent
      logging failures from crashing the application.

    **Performance Note:**
    The google-cloud-logging library uses background threads and batching
    by default when using the Client() API. Log messages are queued and
    sent asynchronously, minimizing impact on application latency.

    Args:
        log_name: The log name in GCP Cloud Logging (default: "crypto-sentinel")

    Returns:
        bool: True if GCP logging was successfully initialized, False otherwise
    """
    try:
        from google.cloud import logging as gcp_logging

        client = gcp_logging.Client()
        gcp_logger = client.logger(log_name)
    except Exception as e:
        # Log to Rich console since GCP isn't available
        logger.warning(
            f"Failed to initialize GCP Cloud Logging client: {e}. "
            "Application will continue with Rich terminal logging only.",
            extra={"error": str(e), "log_name": log_name},
        )
        return False

    def gcp_sink(message) -> None:
        """
        Loguru sink that sends structured logs to GCP Cloud Logging.

        Preserves all extra context fields as searchable jsonPayload fields.
        Exceptions are caught to prevent logging failures from crashing the app.
        """
        try:
            record = message.record
            severity = LOGURU_TO_GCP_SEVERITY.get(record["level"].name, "DEFAULT")

            # Build structured payload with core fields
            payload = {
                "message": record["message"],
                "level": record["level"].name,
                "timestamp": record["time"].isoformat(),
                "module": record["module"],
                "function": record["function"],
                "line": record["line"],
            }

            # Merge sanitized extra context (symbol, qty, pnl_usd, asset_class, etc.)
            # Sanitization ensures all values are JSON-serializable
            if record["extra"]:
                sanitized_extra = _sanitize_extra_context(record["extra"])
                payload.update(sanitized_extra)

            # Send to GCP Cloud Logging with mapped severity
            # This uses the library's built-in background batching
            gcp_logger.log_struct(payload, severity=severity)
        except Exception:
            # Silently ignore logging failures to prevent cascading errors
            # The Rich terminal sink will still capture these logs
            pass

    # Add GCP sink - this is ADDITIVE, does NOT remove Rich sink
    logger.add(gcp_sink, format="{message}", level="DEBUG")
    logger.info("GCP Cloud Logging sink initialized", extra={"log_name": log_name})
    return True


# =============================================================================
# PROGRESS VISUALIZATION
# =============================================================================


@contextmanager
def create_portfolio_progress(
    total: int, description: str = "Processing portfolio..."
) -> Iterator[Tuple[Progress, Any]]:
    """
    Create a Rich progress bar for portfolio processing.

    Args:
        total: Total number of items to process
        description: Initial description text

    Yields:
        Tuple of (Progress instance, task_id) for updating progress

    Example:
        with create_portfolio_progress(len(portfolio)) as (progress, task):
            for symbol in portfolio:
                progress.update(task, description=f"Analyzing {symbol}...")
                # ... process symbol ...
                progress.advance(task)
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,  # Keep progress bar visible after completion
    )

    with progress:
        task = progress.add_task(description, total=total)
        yield progress, task


def create_status_spinner(description: str = "Processing...") -> Progress:
    """
    Create a simple status spinner for indeterminate operations.

    Returns:
        Progress instance configured as a spinner
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        console=console,
        transient=True,
    )


# =============================================================================
# EXECUTION SUMMARY TABLE
# =============================================================================


def create_execution_summary_table(
    total_duration: float,
    symbols_processed: int,
    total_symbols: int,
    signals_found: int,
    symbol_results: Optional[List[Dict[str, Any]]] = None,
    avg_slippage_pct: Optional[float] = None,
) -> Table:
    """
    Create a Rich table for the execution summary.

    Args:
        total_duration: Total execution time in seconds
        symbols_processed: Number of symbols successfully processed
        total_symbols: Total number of symbols in portfolio
        signals_found: Number of trading signals detected
        symbol_results: Optional list of per-symbol results for detailed table
        avg_slippage_pct: Optional average entry slippage percentage

    Returns:
        Rich Table object ready to be printed
    """
    # Get total errors from the single source of truth: the metrics collector
    metrics = get_metrics_collector()
    metrics_summary = metrics.get_summary()
    total_errors = sum(
        stats.get("failure_count", 0) for stats in metrics_summary.values()
    )

    # Summary statistics table
    summary_table = Table(
        title="📊 EXECUTION SUMMARY",
        title_style="bold cyan",
        show_header=True,
        header_style="bold magenta",
    )

    summary_table.add_column("Metric", style="cyan", width=25)
    summary_table.add_column("Value", justify="right", style="green", width=20)

    # Calculate success rate
    success_rate = (
        (symbols_processed - total_errors) / symbols_processed * 100
        if symbols_processed > 0
        else 0
    )

    summary_table.add_row("⏱️  Total Duration", f"{total_duration:.2f}s")
    summary_table.add_row("📈 Symbols Processed", f"{symbols_processed}/{total_symbols}")
    summary_table.add_row("🎯 Signals Found", str(signals_found))
    summary_table.add_row(
        "❌ Errors Encountered",
        f"[red]{total_errors}[/red]" if total_errors > 0 else "0",
    )
    summary_table.add_row("✅ Success Rate", f"{success_rate:.1f}%")

    # Add average slippage if available
    if avg_slippage_pct is not None:
        # Color code: green for favorable (negative), red for unfavorable (>0.5%)
        if avg_slippage_pct > 0.5:
            slippage_style = "[red]"
        elif avg_slippage_pct < 0:
            slippage_style = "[green]"
        else:
            slippage_style = "[yellow]"
        summary_table.add_row(
            "📉 Avg Entry Slippage",
            f"{slippage_style}{avg_slippage_pct:+.3f}%[/]",
        )

    return summary_table


def create_symbol_results_table(
    results: List[Dict[str, Any]],
) -> Table:
    """
    Create a detailed table of per-symbol processing results.

    Args:
        results: List of dicts with keys: symbol, asset_class, status, pattern, duration

    Returns:
        Rich Table with symbol-level details
    """
    table = Table(
        title="📋 Symbol Processing Details",
        title_style="bold blue",
        show_header=True,
        header_style="bold white",
    )

    table.add_column("Symbol", style="magenta", width=12)
    table.add_column("Asset Class", style="cyan", width=10)
    table.add_column("Status", width=12)
    table.add_column("Pattern", style="yellow", width=20)
    table.add_column("Duration", justify="right", width=10)

    for r in results:
        status = r.get("status", "OK")
        status_styled = (
            f"[green]✅ {status}[/green]" if status == "OK" else f"[red]❌ {status}[/red]"
        )
        pattern = r.get("pattern", "-")
        pattern_styled = f"[bold cyan]{pattern}[/bold cyan]" if pattern != "-" else "-"

        table.add_row(
            r.get("symbol", ""),
            r.get("asset_class", ""),
            status_styled,
            pattern_styled,
            f"{r.get('duration', 0):.2f}s",
        )

    return table


# =============================================================================
# ERROR HIGHLIGHTING
# =============================================================================


def log_critical_situation(
    situation: str,
    details: str,
    suggestion: Optional[str] = None,
) -> None:
    """
    Display a highlighted panel for critical error situations.

    Args:
        situation: Short description (e.g., "DATABASE DRIFT DETECTED")
        details: Detailed error information
        suggestion: Optional suggestion for resolution
    """
    content = f"[bold red]{situation}[/bold red]\n\n{details}"

    if suggestion:
        content += f"\n\n[dim]💡 Suggestion: {suggestion}[/dim]"

    panel = Panel(
        content,
        title="⚠️ CRITICAL SITUATION",
        border_style="red",
        padding=(1, 2),
    )
    console.print(panel)


def log_validation_error(doc_id: str, error: Exception) -> None:
    """
    Display highlighted panel for validation errors (database drift).

    Args:
        doc_id: Document ID that failed validation
        error: The validation error that occurred
    """
    log_critical_situation(
        situation="DATABASE DRIFT DETECTED",
        details=f"Document: [bold]{doc_id}[/bold]\n\nError: {error}",
        suggestion="Legacy document will be auto-deleted. Check data migration status.",
    )


def log_api_error(endpoint: str, error: Exception) -> None:
    """
    Display highlighted panel for API errors.

    Args:
        endpoint: API endpoint that failed
        error: The API error that occurred
    """
    log_critical_situation(
        situation="API ERROR",
        details=f"Endpoint: [bold]{endpoint}[/bold]\n\nError: {error}",
        suggestion="Check API credentials and rate limits.",
    )


# =============================================================================
# STRUCTURED LOGGER (Legacy Compatibility)
# =============================================================================


class StructuredLogger:
    """Wrapper for adding structured context to Python logging."""

    def __init__(self, name: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize structured logger.

        Args:
            name: Logger name (typically __name__)
            context: Default context to include in all log messages
        """
        self.context = context or {}
        self.logger = logger.bind(**self.context)

    def _format_message(
        self, msg: str, extra_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format message with context."""
        context = {**self.context, **(extra_context or {})}
        if context:
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            return f"{msg} | {context_str}"
        return msg

    def debug(self, msg: str, **context):
        """Log debug message with context."""
        self.logger.debug(self._format_message(msg, context))

    def info(self, msg: str, **context):
        """Log info message with context."""
        self.logger.info(self._format_message(msg, context))

    def warning(self, msg: str, **context):
        """Log warning message with context."""
        self.logger.warning(self._format_message(msg, context))

    def error(self, msg: str, exc_info=False, **context):
        """Log error message with context."""
        if exc_info:
            self.logger.opt(exception=True).error(self._format_message(msg, context))
        else:
            self.logger.error(self._format_message(msg, context))

    def critical(self, msg: str, exc_info=False, **context):
        """Log critical message with context."""
        if exc_info:
            self.logger.opt(exception=True).critical(self._format_message(msg, context))
        else:
            self.logger.critical(self._format_message(msg, context))

    def add_context(self, **context):
        """Add persistent context to this logger."""
        self.context.update(context)
        self.logger = logger.bind(**self.context)

    def remove_context(self, *keys):
        """Remove keys from persistent context."""
        for key in keys:
            self.context.pop(key, None)
        self.logger = logger.bind(**self.context)


# =============================================================================
# TIMING UTILITIES
# =============================================================================


@contextmanager
def log_execution_time(logger_instance: Any, operation: str, **context):
    """
    Context manager to log execution time of an operation.

    Args:
        logger_instance: Logger instance (StructuredLogger, loguru logger, or std logger)
        operation: Name of the operation being timed
        **context: Additional context to include in log messages
    """
    context_str = " | ".join(f"{k}={v}" for k, v in context.items()) if context else ""
    full_context = f" | {context_str}" if context_str else ""

    start_time = time.time()
    logger_instance.info(f"Starting: {operation}{full_context}")

    try:
        yield
    except Exception as e:
        elapsed = time.time() - start_time
        msg = f"Failed: {operation} | duration={elapsed:.2f}s{full_context} | error={str(e)}"

        if hasattr(logger_instance, "opt"):  # Loguru
            logger_instance.opt(exception=True).error(msg)
        elif hasattr(logger_instance, "error"):
            try:
                logger_instance.error(msg, exc_info=True)
            except TypeError:
                logger_instance.error(msg)
        else:
            print(f"ERROR: {msg}")

        raise
    else:
        elapsed = time.time() - start_time
        logger_instance.info(
            f"Completed: {operation} | duration={elapsed:.2f}s{full_context}"
        )


def timed(operation_name: Optional[str] = None) -> Callable[..., Any]:
    """
    Decorator to automatically log execution time of a function.
    """

    def decorator(func):
        op_name = operation_name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                logger.info(f"Starting: {op_name}")
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                logger.info(f"Completed: {op_name} | duration={elapsed:.2f}s")
                return result
            except Exception as e:
                elapsed = time.time() - start_time
                logger.opt(exception=True).error(
                    f"Failed: {op_name} | duration={elapsed:.2f}s | error={str(e)}"
                )
                raise

        return wrapper

    return decorator


# =============================================================================
# METRICS COLLECTOR
# =============================================================================


class MetricsCollector:
    """
    Simple metrics collector for tracking operation statistics.

    This provides basic metrics tracking. For production, consider using
    Prometheus client library or Cloud Monitoring.
    """

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: Dict[str, Dict[str, Any]] = {}
        # Risk Metrics
        self.risk_counts: Dict[str, int] = {}
        self.capital_protected: float = 0.0
        self.blocked_symbols: set[str] = set()
        self._lock = threading.Lock()

    def record_risk_block(self, gate: str, symbol: str, amount: float = 0.0):
        """
        Record a trade blocked by risk gates.

        Args:
            gate: The name of the gate (e.g., "drawdown", "sector_cap")
            symbol: The symbol being blocked
            amount: The estimated capital that was protected (prevented from being risked)
        """
        with self._lock:
            self.risk_counts[gate] = self.risk_counts.get(gate, 0) + 1
            self.capital_protected += amount
            self.blocked_symbols.add(symbol)

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get summary of risk metrics."""
        return {
            "by_gate": self.risk_counts,
            "total_blocked": sum(self.risk_counts.values()),
            "capital_protected": self.capital_protected,
            "blocked_symbols": sorted(list(self.blocked_symbols)),
        }

    def _initialize_operation_metrics(self, operation: str):
        """Initialize metrics for a new operation if not present."""
        if operation not in self.metrics:
            self.metrics[operation] = {
                "success_count": 0,
                "failure_count": 0,
                "total_duration": 0.0,
                "min_duration": float("inf"),
                "max_duration": 0.0,
            }

    def record_success(self, operation: str, duration: float):
        """Record successful operation."""
        with self._lock:
            self._initialize_operation_metrics(operation)
            m = self.metrics[operation]
            m["success_count"] += 1
            m["total_duration"] += duration
            m["min_duration"] = min(m["min_duration"], duration)
            m["max_duration"] = max(m["max_duration"], duration)

    def record_failure(self, operation: str, duration: float):
        """Record failed operation."""
        with self._lock:
            self._initialize_operation_metrics(operation)
            m = self.metrics[operation]
            m["failure_count"] += 1
            m["total_duration"] += duration

    def get_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics summary."""
        summary = {}
        for operation, m in self.metrics.items():
            total_ops = m["success_count"] + m["failure_count"]
            avg_duration = m["total_duration"] / total_ops if total_ops > 0 else 0.0

            summary[operation] = {
                "total_operations": total_ops,
                "success_count": m["success_count"],
                "failure_count": m["failure_count"],
                "success_rate": (
                    m["success_count"] / total_ops * 100 if total_ops > 0 else 0.0
                ),
                "avg_duration_seconds": round(avg_duration, 2),
                "min_duration_seconds": (
                    round(m["min_duration"], 2)
                    if m["min_duration"] != float("inf")
                    else None
                ),
                "max_duration_seconds": round(m["max_duration"], 2),
            }

        return summary

    def log_summary(self, logger_instance: Any):
        """Log metrics summary using Rich table."""
        summary = self.get_summary()
        risk_summary = self.get_risk_summary()

        if not summary and not risk_summary["total_blocked"]:
            logger_instance.info("No metrics recorded")
            return

        # 1. Operational Metrics Table
        if summary:
            table = Table(
                title="📈 METRICS SUMMARY",
                title_style="bold green",
                show_header=True,
                header_style="bold white",
            )

            table.add_column("Operation", style="cyan", width=20)
            table.add_column("Total", justify="right", width=8)
            table.add_column("Success", justify="right", style="green", width=8)
            table.add_column("Failed", justify="right", style="red", width=8)
            table.add_column("Rate", justify="right", width=10)
            table.add_column("Avg Time", justify="right", width=10)

            for operation, stats in summary.items():
                table.add_row(
                    operation,
                    str(stats["total_operations"]),
                    str(stats["success_count"]),
                    str(stats["failure_count"]),
                    f"{stats['success_rate']:.1f}%",
                    f"{stats['avg_duration_seconds']}s",
                )

            console.print(table)
            console.print()  # Spacer

        # 2. Risk Metrics Table (if any risk blocks)
        if risk_summary["total_blocked"] > 0:
            risk_table = Table(
                title="🛡️ RISK GATES SUMMARY",
                title_style="bold red",
                show_header=True,
                header_style="bold white",
            )
            risk_table.add_column("Metric", style="yellow", width=25)
            risk_table.add_column("Value", justify="right", style="white", width=20)

            risk_table.add_row("Total Trades Blocked", str(risk_summary["total_blocked"]))
            risk_table.add_row(
                "Capital Protected", f"${risk_summary['capital_protected']:.2f}"
            )

            # Breakdown by gate
            for gate, count in risk_summary["by_gate"].items():
                risk_table.add_row(f"Blocked by {gate}", str(count))

            console.print(risk_table)

            # Persist to Logs (for CloudWatch/GCP Metrics)
            logger_instance.info(
                "Risk Metrics Summary",
                extra={
                    "metric_type": "risk_summary",
                    "total_blocked": risk_summary["total_blocked"],
                    "capital_protected": risk_summary["capital_protected"],
                    "by_gate": risk_summary["by_gate"],
                    "blocked_symbols": risk_summary["blocked_symbols"],
                },
            )


# Global metrics collector instance
_global_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    return _global_metrics
