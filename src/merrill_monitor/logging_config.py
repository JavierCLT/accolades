from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(level: str | None = None, log_file: str | None = None) -> None:
    resolved_level = getattr(logging, (level or os.getenv("LOG_LEVEL") or "INFO").upper(), logging.INFO)
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    target_file = log_file if log_file is not None else os.getenv("LOG_FILE")
    if target_file:
        path = Path(target_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3))

    logging.basicConfig(
        level=resolved_level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=handlers,
        force=True,
    )
