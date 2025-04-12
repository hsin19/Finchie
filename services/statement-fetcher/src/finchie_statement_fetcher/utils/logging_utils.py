import logging
import sys


def setup_console_logger(logger: logging.Logger) -> None:
    """
    Set up console logging for the given logger with standard format.

    Args:
        logger: The logger instance to configure
    """
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
