import os
import subprocess
from typing import Any, Dict

from crypto_signals.config import Settings


def get_git_hash() -> str:
    """
    Get the short git hash of the current revision.
    Returns 'unknown' if git command fails.
    """
    # 1. Try Environment Variables first (Fastest / Docker friendly)
    env_hash = os.getenv("GIT_SHA") or os.getenv("COMMIT_SHA") or os.getenv("REVISION_ID")
    if env_hash:
        return env_hash

    # 2. Try git command (Local Development)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        # Suppress error in logs - likely just missing .git folder in container
        return "unknown"


def get_job_context(settings: Settings) -> Dict[str, Any]:
    """
    Extract critical configuration settings for job metadata.
    """
    critical_settings = {
        "ENVIRONMENT",
        "TEST_MODE",
        "MAX_CRYPTO_POSITIONS",
        "MAX_EQUITY_POSITIONS",
        "RISK_PER_TRADE",
        "ENABLE_EXECUTION",
        "ALPACA_PAPER_TRADING",
    }
    return settings.model_dump(include=critical_settings)
