from __future__ import annotations

import sys
from typing import Any

from loguru import logger


def configure_logging(sink: Any = sys.stderr) -> None:
    logger.remove()
    logger.add(sink, diagnose=False, backtrace=False)
