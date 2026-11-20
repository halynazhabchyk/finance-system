"""One logging setup for every service, so INFO logs of app and shared modules are visible."""

from __future__ import annotations

import logging
from typing import TextIO

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(stream: TextIO | None = None) -> None:
    """Root handler at INFO; ``stream`` defaults to stderr (required by the MCP stdio transport)."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=stream)
