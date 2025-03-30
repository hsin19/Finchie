import logging
import sys
from io import StringIO

import pytest

from finchie_data_pipeline.utils.logging_utils import setup_console_logger


@pytest.fixture
def test_logger():
    """Create a clean test logger"""
    logger = logging.getLogger("test_logger")
    logger.handlers = []
    return logger


def test_setup_console_logger(test_logger):
    """Test logger configuration"""
    setup_console_logger(test_logger)

    assert test_logger.level == logging.DEBUG
    assert len(test_logger.handlers) == 1

    handler = test_logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream == sys.stdout

    formatter = handler.formatter
    assert formatter._fmt == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def test_logger_output(test_logger, mocker):
    """Test actual logger output"""
    mock_stdout = mocker.patch("sys.stdout", new_callable=StringIO)
    setup_console_logger(test_logger)

    test_message = "Test log message"
    test_logger.info(test_message)

    output = mock_stdout.getvalue()
    assert test_message in output
    assert "INFO" in output
    assert "test_logger" in output
