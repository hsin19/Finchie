from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum


class Kind(StrEnum):
    PURCHASE = "purchase"
    FOREIGN_TRANSACTION_FEE = "foreign_transaction_fee"
    ANNUAL_FEE = "annual_fee"
    REFUND = "refund"
    REBATE = "rebate"
    PAYMENT = "payment"


@dataclass(frozen=True)
class Transaction:
    transaction_date: date
    description: str
    kind: Kind
    amount: Decimal
    posting_date: date | None = None
    original_amount: Decimal | None = None
    original_currency: str = ""
    country: str = ""
    card_last4: str = ""


@dataclass(frozen=True)
class Reconciliation:
    computed: Decimal
    stated: Decimal
    stated_label: str

    @property
    def balanced(self) -> bool:
        return self.computed == self.stated


@dataclass(frozen=True)
class Statement:
    institution: str
    closing_date: date
    due_date: date
    currency: str
    total_due: Decimal
    transactions: list[Transaction]
    reconciliation: Reconciliation


@dataclass(frozen=True)
class ParseResult:
    parser: str
    parser_version: str
    statement: Statement
    warnings: list[str] = field(default_factory=list)
