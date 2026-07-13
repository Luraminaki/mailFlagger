import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from mailflagger.logging_utils import configure_logging, reset_logging


def test_configure_logging_creates_log_file(tmp_path: Path):
    stem = str(tmp_path / 'mytest')

    configure_logging(log_file_stem=stem)
    logging.getLogger('test').info('hello')

    assert Path(f'{stem}.log').exists()


def test_configure_logging_creates_missing_parent_directory(tmp_path: Path):
    stem = str(tmp_path / 'nested' / 'deep' / 'mytest')

    configure_logging(log_file_stem=stem)

    assert Path(f'{stem}.log').exists()


def test_reset_logging_closes_the_file_handler(tmp_path: Path):
    stem = str(tmp_path / 'mytest')
    configure_logging(log_file_stem=stem)
    root = logging.getLogger()
    file_handler = next(h for h in root.handlers if isinstance(h, RotatingFileHandler))
    stream = file_handler.stream

    reset_logging()

    assert stream.closed


def test_configure_logging_twice_does_not_break_rotation(tmp_path: Path):
    stem = str(tmp_path / 'mytest')

    configure_logging(log_file_stem=stem, max_bytes=200, backup_count=2)
    configure_logging(log_file_stem=stem, max_bytes=200, backup_count=2)

    logger = logging.getLogger('test_rotation')
    for _ in range(50):
        logger.info('x' * 50)

    assert Path(f'{stem}.log').exists()
