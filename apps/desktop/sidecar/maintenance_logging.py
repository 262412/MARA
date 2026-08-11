from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

MAINTENANCE_LOGGER = "mara.desktop.index_tasks"


def configure_maintenance_logging(data_root: Path) -> RotatingFileHandler:
    log_directory = data_root.expanduser().resolve() / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / "indexing.log"
    log_path.touch(mode=0o600, exist_ok=True)
    log_path.chmod(0o600)
    handler = RotatingFileHandler(
        log_path,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger = logging.getLogger(MAINTENANCE_LOGGER)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler
