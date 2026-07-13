#!/usr/bin/env python3
"""Shared logging setup: a rotating file handler plus console output."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_DEFAULT_MAX_BYTES = 5 * 1024 * 1024
_DEFAULT_BACKUP_COUNT = 5


def reset_logging() -> None:
    """Removes and closes every handler/filter on the root logger.

    Called before (re)configuring logging so repeated calls - e.g. across test runs - don't
    stack duplicate handlers, duplicate every log line, or leak the previous handlers' file
    descriptors (an unclosed `RotatingFileHandler` can't be renamed on its next rollover).
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
        handler.close()
    for log_filter in root.filters[:]:
        root.removeFilter(log_filter)


def configure_logging(log_file_stem: str = 'mailflagger', level: int | str = logging.INFO,
                       max_bytes: int = _DEFAULT_MAX_BYTES, backup_count: int = _DEFAULT_BACKUP_COUNT) -> None:
    """Configures root logging once: a rotating file handler plus console output.

    Creates the log file's parent directory if it doesn't already exist. The console handler's
    stream is reconfigured to UTF-8 where supported, so it doesn't mangle non-Latin-1 characters
    that the log file (already UTF-8) renders correctly.

    Args:
        log_file_stem (str): Stem for the rotating log file (`<stem>.log`, `.log.1`, ...).
        level (int | str): Logging level for the root logger, as an int or a level name (e.g. `"INFO"`).
        max_bytes (int): Size a log file may reach before it rotates.
        backup_count (int): Number of rotated log files to keep.
    """
    reset_logging()

    log_path = Path(f'{log_file_stem}.log')
    log_path.parent.mkdir(parents=True, exist_ok=True)

    console_handler = logging.StreamHandler()
    if hasattr(console_handler.stream, 'reconfigure'):
        console_handler.stream.reconfigure(encoding='utf-8', errors='backslashreplace')

    logging.basicConfig(
        level=level,
        format='[%(asctime)s] [%(process)s] [%(name)s] [%(levelname)s]: %(funcName)s -- %(message)s',
        handlers=[
            RotatingFileHandler(log_path, mode='a', maxBytes=max_bytes,
                                 backupCount=backup_count, encoding='utf-8'),
            console_handler,
        ],
    )
