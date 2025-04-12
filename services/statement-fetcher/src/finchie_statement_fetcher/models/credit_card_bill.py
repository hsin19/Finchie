from dataclasses import dataclass
from datetime import date

from .credit_card_statement import CreditCardStatement
from .statement_source import StatementSource


@dataclass
class CreditCardBill:
    """Credit card bill summary information"""

    statement_period_end: date
    """End date of the statement period"""

    payment_due_date: date
    """Date by which payment must be made"""

    total_due_amount: float
    """Total amount due for this billing cycle"""

    minimum_payment_due: float
    """Minimum payment required"""

    previous_balance: float
    """Previous unpaid balance"""

    new_charges: float
    """New charges in this billing cycle"""

    statement_period_start: date | None = None
    """Start date of the statement period"""

    payment_received: float | None = None
    """Payments received during this billing cycle"""

    credit_limit: float | None = None
    """Total credit limit on the card"""

    available_credit: float | None = None
    """Available credit remaining"""

    cardholder_name: str | None = None
    """Name of the primary cardholder"""

    card_last_four: str | None = None
    """Last four digits of the card number"""

    statement: CreditCardStatement | None = None
    """Detailed statement with all transactions"""

    source: StatementSource | None = None
    """Source information for this bill""" 