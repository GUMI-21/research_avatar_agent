"""Application logging interface."""

from loguru import logger as log

from logs.config import configure_logging

__all__ = ["configure_logging", "log"]
