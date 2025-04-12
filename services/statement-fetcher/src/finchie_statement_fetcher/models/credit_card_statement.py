from dataclasses import dataclass

from .credit_card_transaction import CreditCardTransaction


@dataclass
class CreditCardStatement:
    """Credit card statement details"""

    transactions: list[CreditCardTransaction]
    """List of all transactions in this statement""" 