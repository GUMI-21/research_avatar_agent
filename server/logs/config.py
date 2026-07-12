"""Central logging configuration for the server process."""

import logging
import sys
from pathlib import Path
from typing import Union

from loguru import logger

from app.core.settings import LoggingSettings

CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "pid={process.id} thread={thread.name} | "
    "{name}:{function}:{line} | {message}"
)


class InterceptHandler(logging.Handler):
    """Forward standard-library log records to Loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: Union[str, int] = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging(config: LoggingSettings) -> Path:
    """Configure console and rotating file logs, then return the log path."""
    level = config.level.upper()
    log_dir = config.directory.expanduser()

    try:
        logger.level(level)
    except ValueError as exc:
        raise ValueError(f"Invalid logging level: {level}") from exc

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Unable to create log directory: {log_dir}") from exc

    log_path = log_dir / config.file_name

    logger.remove()
    if config.console:
        logger.add(
            sys.stderr,
            level=level,
            format=CONSOLE_FORMAT,
            colorize=sys.stderr.isatty(),
            enqueue=True,
            backtrace=False,
            diagnose=False,
        )
    logger.add(
        log_path,
        level=level,
        format=FILE_FORMAT,
        rotation=config.rotation,
        retention=config.retention,
        compression=config.compression,
        encoding="utf-8",
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        standard_logger = logging.getLogger(logger_name)
        standard_logger.handlers.clear()
        standard_logger.propagate = True

    return log_path
