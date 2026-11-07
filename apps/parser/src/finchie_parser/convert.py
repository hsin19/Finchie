"""Internal model -> generated proto messages."""

from datetime import date
from decimal import Decimal

from google.type import date_pb2, decimal_pb2

from finchie.parser.v1 import parser_pb2 as pb
from finchie_parser.model import Kind, ParseResult, Statement, Transaction

_KINDS = {
    Kind.PURCHASE: pb.TRANSACTION_KIND_PURCHASE,
    Kind.FOREIGN_TRANSACTION_FEE: pb.TRANSACTION_KIND_FOREIGN_TRANSACTION_FEE,
    Kind.ANNUAL_FEE: pb.TRANSACTION_KIND_ANNUAL_FEE,
    Kind.REFUND: pb.TRANSACTION_KIND_REFUND,
    Kind.REBATE: pb.TRANSACTION_KIND_REBATE,
    Kind.PAYMENT: pb.TRANSACTION_KIND_PAYMENT,
}


def to_response(result: ParseResult) -> pb.ParseDocumentResponse:
    return pb.ParseDocumentResponse(
        parser=result.parser,
        parser_version=result.parser_version,
        statement=_statement(result.statement),
        warnings=result.warnings,
    )


def _statement(statement: Statement) -> pb.Statement:
    reconciliation = statement.reconciliation
    return pb.Statement(
        institution=statement.institution,
        closing_date=_date(statement.closing_date),
        due_date=_date(statement.due_date),
        currency=statement.currency,
        total_due=_decimal(statement.total_due),
        transactions=[_transaction(tx) for tx in statement.transactions],
        reconciliation=pb.Reconciliation(
            balanced=reconciliation.balanced,
            computed=_decimal(reconciliation.computed),
            stated=_decimal(reconciliation.stated),
            stated_label=reconciliation.stated_label,
        ),
    )


def _transaction(tx: Transaction) -> pb.Transaction:
    message = pb.Transaction(
        transaction_date=_date(tx.transaction_date),
        description=tx.description,
        kind=_KINDS[tx.kind],
        amount=_decimal(tx.amount),
        original_currency=tx.original_currency,
        country=tx.country,
        card_last4=tx.card_last4,
    )
    if tx.posting_date is not None:
        message.posting_date.CopyFrom(_date(tx.posting_date))
    if tx.original_amount is not None:
        message.original_amount.CopyFrom(_decimal(tx.original_amount))
    return message


def _date(value: date) -> date_pb2.Date:
    return date_pb2.Date(year=value.year, month=value.month, day=value.day)


def _decimal(value: Decimal) -> decimal_pb2.Decimal:
    # Fixed-point notation: google.type.Decimal allows exponents, but consumers rarely parse them.
    return decimal_pb2.Decimal(value=format(value, "f"))
