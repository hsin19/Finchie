from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import Any


class StatementType(IntEnum):
    CREDIT_CARD_BILL = 1


class SourceType(IntEnum):
    CREDIT_CARD = 1


@dataclass
class PaymentSource:
    type: str
    transaction_id: str
    statement_id: str


@dataclass
class Transaction:
    id: str
    description: str
    amount: float
    date: datetime
    statement_id: str | None = None
    payment_source: PaymentSource | None = None


@dataclass
class Statement:
    id: str = ""
    type: StatementType = StatementType.CREDIT_CARD_BILL
    source_type: SourceType = SourceType.CREDIT_CARD
    source_name: str = ""
    source_id: str | None = None
    total_amount: float = 0.0
    previous_amount: float | None = None
    previous_paid: float | None = None
    previous_unpaid: float | None = None
    current_amount: float | None = None
    currency: str = ""
    payment_due_date: datetime | None = None
    transactions: list[Transaction] = field(default_factory=list)
    extra: Any | None = None
