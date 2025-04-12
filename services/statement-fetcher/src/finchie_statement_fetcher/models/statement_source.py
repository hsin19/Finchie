from dataclasses import dataclass
from datetime import date


@dataclass
class StatementSource:
    """Statement source information"""

    source_type: str
    """Type of source (e.g., gmail, pdf, screenshot)"""

    identifier: str | None = None
    """Identifier for the source (e.g., Gmail subject line or file name)"""

    received_date: date | None = None
    """Date when the statement was received""" 