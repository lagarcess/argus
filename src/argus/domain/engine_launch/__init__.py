from .models import LaunchBacktestRequest, LaunchExecutionEnvelope

__all__ = [
    "LaunchBacktestRequest",
    "LaunchExecutionAdapterResult",
    "LaunchExecutionEnvelope",
    "run_launch_backtest",
]


def __getattr__(name: str):
    if name in {"LaunchExecutionAdapterResult", "run_launch_backtest"}:
        from .adapter import LaunchExecutionAdapterResult, run_launch_backtest

        exports = {
            "LaunchExecutionAdapterResult": LaunchExecutionAdapterResult,
            "run_launch_backtest": run_launch_backtest,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
