from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Amount:
    """Amount information"""

    amount: Decimal
    """The numerical value of the amount"""

    currency: str
    """Currency code (e.g., TWD, USD)""" 