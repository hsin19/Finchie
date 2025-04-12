from dataclasses import dataclass


@dataclass
class CardDetails:
    """Credit card details"""

    card_type: str | None = None
    """Card type (e.g., Visa, Mastercard)"""

    card_nickname: str | None = None
    """User-defined nickname for the card"""

    card_last_four: str | None = None
    """Last four digits of the card number"""

    cardholder_name: str | None = None
    """Name of the cardholder""" 