import logging

import pytest

from mailflagger.logging_utils import reset_logging


@pytest.fixture(autouse=True)
def isolate_root_logger():
    """Prevents configure_logging()/reset_logging() in one test from leaking handler or
    level state into another test running later in the same pytest process."""
    root = logging.getLogger()
    original_level = root.level
    yield
    reset_logging()
    root.setLevel(original_level)
