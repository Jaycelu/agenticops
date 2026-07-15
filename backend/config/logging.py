from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from config.settings import settings


def setup_logging():
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.log_level.upper(),
        serialize=settings.log_json,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
    if settings.log_file_enabled:
        log_dir = Path(__file__).resolve().parents[1] / "logs"
        log_dir.mkdir(exist_ok=True)
        logger.add(
            log_dir / "app.jsonl",
            rotation="100 MB",
            retention="30 days",
            serialize=True,
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )
    return logger
