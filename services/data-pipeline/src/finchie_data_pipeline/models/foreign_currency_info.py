from dataclasses import dataclass
from datetime import date


@dataclass
class ForeignCurrencyInfo:
    """Foreign currency transaction information"""

    exchange_rate: float | None = None
    """The exchange rate used for the transaction"""

    exchange_date: date | None = None
    """Date when the exchange rate was applied""" 