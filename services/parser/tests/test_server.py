from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc

from finchie.parser.v1 import parser_pb2 as pb
from finchie.parser.v1 import parser_pb2_grpc
from finchie_parser import server as server_module
from finchie_parser.model import Kind, ParseResult, Reconciliation, Statement, Transaction
from finchie_parser.settings import Settings


@pytest.fixture
def channel() -> Iterator[grpc.Channel]:
    server, port = server_module.build_server(Settings(ocr=False, workers=1), None, "127.0.0.1:0")
    server.start()
    with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
        yield channel
    server.stop(grace=None)


def parse(channel: grpc.Channel, content: bytes, content_type: str) -> pb.ParseDocumentResponse:
    stub = parser_pb2_grpc.ParserServiceStub(channel)
    request = pb.ParseDocumentRequest(document_id="d1", filename="doc", content_type=content_type, content=content)
    return stub.ParseDocument(request, timeout=10)


def status_of(channel: grpc.Channel, content: bytes, content_type: str) -> grpc.StatusCode:
    with pytest.raises(grpc.RpcError) as error:
        parse(channel, content, content_type)
    return error.value.code()


def test_empty_document_is_invalid_argument(channel: grpc.Channel) -> None:
    assert status_of(channel, b"", "application/pdf") is grpc.StatusCode.INVALID_ARGUMENT


def test_unknown_content_is_unimplemented(channel: grpc.Channel) -> None:
    assert status_of(channel, b"\x89PNG", "image/png") is grpc.StatusCode.UNIMPLEMENTED


def test_health_reports_serving(channel: grpc.Channel) -> None:
    stub = health_pb2_grpc.HealthStub(channel)
    response = stub.Check(health_pb2.HealthCheckRequest(service=server_module.SERVICE_NAME), timeout=5)
    assert response.status == health_pb2.HealthCheckResponse.SERVING


def test_result_is_converted_to_proto(channel: grpc.Channel, monkeypatch: pytest.MonkeyPatch) -> None:
    statement = Statement(
        institution="hsbc",
        closing_date=date(2026, 10, 21),
        due_date=date(2026, 11, 8),
        currency="TWD",
        total_due=Decimal("95730"),
        transactions=[
            Transaction(
                transaction_date=date(2026, 10, 8),
                posting_date=date(2026, 10, 9),
                description="SHOP",
                kind=Kind.PURCHASE,
                amount=Decimal(28009),
                original_amount=Decimal("780.00"),
                original_currency="EUR",
                country="IT",
            ),
            Transaction(date(2026, 9, 23), "PAYMENT", Kind.PAYMENT, Decimal(-69019)),
        ],
        reconciliation=Reconciliation(Decimal(28009), Decimal(28009), "new charges"),
    )
    monkeypatch.setattr(
        server_module, "parse_document", lambda *_, **__: ParseResult("hsbc.credit_card", "1", statement, [])
    )

    response = parse(channel, b"%PDF", "application/pdf")

    assert (response.parser, response.parser_version) == ("hsbc.credit_card", "1")
    assert response.statement.total_due.value == "95730"
    assert response.statement.reconciliation.balanced
    shop, payment = response.statement.transactions
    assert (shop.amount.value, shop.original_amount.value, shop.original_currency) == ("28009", "780.00", "EUR")
    assert (shop.transaction_date.year, shop.transaction_date.month, shop.transaction_date.day) == (2026, 10, 8)
    assert shop.kind == pb.TRANSACTION_KIND_PURCHASE
    assert payment.kind == pb.TRANSACTION_KIND_PAYMENT
    assert not payment.HasField("posting_date")
    assert not payment.HasField("original_amount")
