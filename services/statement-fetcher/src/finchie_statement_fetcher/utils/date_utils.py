import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


def parse_taiwanese_date(date_str: str) -> datetime | None:
    """
    Parse Taiwanese date format 'YYY/MM/DD' to datetime object.
    YYY is the year based on the founding of the Republic of China (1911).

    Example: 114/04/07 -> 2025-04-07

    Args:
        date_str (str): Date string in Taiwanese format (YYY/MM/DD)

    Returns:
        datetime | None: Converted datetime object or None if parsing fails
    """
    try:
        match = re.match(r"(\d{1,3})/(\d{1,2})/(\d{1,2})", date_str)
        if not match:
            logger.warning("Invalid Taiwanese date format", extra={"date_str": date_str})
            return None

        roc_year, month, day = map(int, match.groups())
        gregorian_year = roc_year + 1911

        return datetime(gregorian_year, month, day)
    except Exception as e:
        logger.warning("Failed to parse Taiwanese date", extra={"date_str": date_str, "error": str(e)})
        return None
