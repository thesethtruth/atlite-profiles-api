from __future__ import annotations

import logging
import os

_DEFAULT_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(level: str | int | None = None) -> None:
    """Configure process-wide logging once with a consistent format."""
    resolved_level = level or os.getenv("LOG_LEVEL", "INFO")

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(resolved_level)
        return

    logging.basicConfig(level=resolved_level, format=_DEFAULT_FORMAT)
