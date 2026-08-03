from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path


def test_live_eval_env_preloads_calendar_aware_confirmation(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    (project / "src" / "argus").mkdir(parents=True)
    (project / "pyproject.toml").write_text(
        '[tool.poetry]\nname = "argus-live-eval-regression"\n',
        encoding="utf-8",
    )
    (project / ".env").write_text(
        "ARGUS_MARKET_DATA_PROVIDER_MODE=synthetic_unit_fixture\n",
        encoding="utf-8",
    )
    eval_env = tmp_path / "live-eval.env"
    eval_env.write_text(
        "ARGUS_MARKET_DATA_PROVIDER_MODE=live_provider\n",
        encoding="utf-8",
    )
    process_env = os.environ.copy()
    process_env.pop("ARGUS_MARKET_DATA_PROVIDER_MODE", None)
    process_env.update(
        {
            "ARGUS_EVAL_ENV_FILE": str(eval_env),
            "ARGUS_RUN_LIVE_EVALS": "1",
            "ARGUS_TEST_PROJECT_ROOT": str(project),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    probe = textwrap.dedent(
        """
        import json
        import os
        from datetime import date, datetime
        from pathlib import Path

        import pandas as pd

        import argus.env as argus_env

        argus_env.__file__ = str(
            Path(os.environ["ARGUS_TEST_PROJECT_ROOT"])
            / "src"
            / "argus"
            / "env.py"
        )
        import tests.evals.test_measurement_eval_live  # noqa: F401
        from argus.domain.backtesting.coverage import prepare_market_data
        from argus.domain.market_data.capabilities import EquityMarketSession

        provider_mode = os.environ["ARGUS_MARKET_DATA_PROVIDER_MODE"]
        if provider_mode == "synthetic_unit_fixture":
            observed_days = pd.date_range(
                start="2024-01-01",
                end="2024-12-31",
                freq="1D",
                tz="UTC",
            )
        else:
            observed_days = pd.bdate_range(
                start="2024-01-02",
                end="2024-12-31",
                tz="UTC",
            )

        def fetch_bars(**_kwargs):
            close = pd.Series(
                range(100, 100 + len(observed_days)),
                index=observed_days,
                dtype=float,
            )
            return pd.DataFrame(
                {
                    "open": close,
                    "high": close + 1.0,
                    "low": close - 1.0,
                    "close": close,
                    "volume": 1_000.0,
                },
                index=observed_days,
            )

        def fetch_calendar(*, start_date: date, end_date: date):
            return tuple(
                EquityMarketSession(
                    provider="calendar-fixture",
                    session_date=timestamp.date(),
                    opens_at=datetime.fromisoformat(
                        f"{timestamp.date().isoformat()}T09:30:00-05:00"
                    ),
                    closes_at=datetime.fromisoformat(
                        f"{timestamp.date().isoformat()}T16:00:00-05:00"
                    ),
                )
                for timestamp in observed_days
                if start_date <= timestamp.date() <= end_date
            )

        prepared = prepare_market_data(
            {
                "asset_class": "equity",
                "symbols": ["AAPL"],
                "timeframe": "1D",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "requested_date_range": {
                    "start": "2024-01-01",
                    "end": "2024-12-31",
                },
                "benchmark_symbol": "SPY",
            },
            fetch_ohlcv_func=fetch_bars,
            fetch_market_calendar_func=fetch_calendar,
        )
        print(
            json.dumps(
                {
                    "provider_mode": provider_mode,
                    "effective_date_range": (
                        prepared.effective_date_range.model_dump()
                    ),
                    "adjustment_reason": prepared.adjustment_reason,
                },
                sort_keys=True,
            )
        )
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).parents[2],
        env=process_env,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    result = json.loads(completed.stdout.strip().splitlines()[-1])

    assert result == {
        "provider_mode": "live_provider",
        "effective_date_range": {
            "start": "2024-01-02",
            "end": "2024-12-31",
        },
        "adjustment_reason": "calendar_alignment",
    }
