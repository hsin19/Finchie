"""Small helpers shared by the bank parsers: ROC dates, amounts, descriptions."""

import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal

_SPACES = re.compile(r"\s+")


def roc_date(text: str) -> date:
    """`115/09/07` (Minguo calendar) -> 2026-09-07."""
    year, month, day = (int(part) for part in text.split("/"))
    return date(year + 1911, month, day)


def iso_date(text: str) -> date:
    """`2026/10/21` -> 2026-10-21."""
    year, month, day = (int(part) for part in text.split("/"))
    return date(year, month, day)


def month_day(text: str, closing: date) -> date:
    """`09/07` dated relative to the statement's closing date.

    Statement lines never postdate the closing date by much, so a date that
    would land more than a month after it belongs to the previous year
    (a December purchase on a January statement).
    """
    month, day = (int(part) for part in text.split("/"))
    try:
        candidate = date(closing.year, month, day)
    except ValueError:  # 02/29 in a non-leap closing year
        return date(closing.year - 1, month, day)
    if candidate > closing + timedelta(days=31):
        return date(closing.year - 1, month, day)
    return candidate


def amount(text: str) -> Decimal:
    """`-6,552.97` -> Decimal('-6552.97')."""
    return Decimal(text.replace(",", ""))


def clean(text: str) -> str:
    """Full-width letters and digits to ASCII, runs of whitespace to one space."""
    return _SPACES.sub(" ", unicodedata.normalize("NFKC", text)).strip()
