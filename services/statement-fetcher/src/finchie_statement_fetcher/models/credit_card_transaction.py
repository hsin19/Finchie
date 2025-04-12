from dataclasses import dataclass
from datetime import date

from .amount import Amount
from .card_details import CardDetails
from .foreign_currency_info import ForeignCurrencyInfo


@dataclass
class CreditCardTransaction:
    """Individual credit card transaction"""

    transaction_date: date
    """Date when the transaction occurred"""

    posting_date: date
    """Date when the transaction was posted to the account"""

    description: str
    """Description of the transaction"""

    billing_amount: Amount
    """Amount billed in the account's currency"""

    original_amount: Amount | None = None
    """Original transaction amount, which may differ from billing amount for foreign transactions"""

    location: str | None = None
    """Location where the transaction occurred"""

    foreign_currency_info: ForeignCurrencyInfo | None = None
    """Information about foreign currency exchange if applicable"""

    card_info: CardDetails | None = None
    """Credit card details for this transaction""" 