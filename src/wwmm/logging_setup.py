"""Logging configuration for the WWMM app and CLI."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(state_dir: Path, *, verbose: bool = False) -> None:
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    log_path = state_dir / "wwmm.log"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    for handler in root.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename) == log_path:
            return

    handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(handler)
