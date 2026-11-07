from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc
from pdfs import blank_pdf, statement_email

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


def test_accepts_a_document_at_the_backend_upload_limit(channel: grpc.Channel) -> None:
    # BACKEND_MAX_UPLOAD_MB is 32: the file alone fills it, and the request carries more fields.
    content = b"\x89PNG" + bytes(32 * 1024 * 1024 - 4)
    assert status_of(channel, content, "image/png") is grpc.StatusCode.UNIMPLEMENTED


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


def test_open_document_returns_the_email_and_its_decrypted_attachments() -> None:
    settings = Settings(ocr=False, workers=1, pdf_passwords={"bank": "secret"})
    server, port = server_module.build_server(settings, None, "127.0.0.1:0")
    server.start()
    try:
        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
            stub = parser_pb2_grpc.ParserServiceStub(channel)
            request = pb.OpenDocumentRequest(
                document_id="d1",
                filename="mail.eml",
                content_type="message/rfc822",
                content=statement_email(blank_pdf("secret")),
            )
            response = stub.OpenDocument(request, timeout=10)
    finally:
        server.stop(grace=None)
    assert response.email.subject == "範例銀行 2026年11月 信用卡電子帳單"
    assert response.email.date.ToDatetime(tzinfo=UTC) == datetime(2026, 11, 6, 1, 30, tzinfo=UTC)
    assert "data:image/png;base64," in response.email.html
    assert [(f.filename, f.content_type, f.locked, f.primary) for f in response.files] == [
        ("帳單_11511.pdf", "application/pdf", False, True),
        ("slip.html", "text/html", False, False),
    ]


def test_open_document_rejects_an_empty_document(channel: grpc.Channel) -> None:
    stub = parser_pb2_grpc.ParserServiceStub(channel)
    request = pb.OpenDocumentRequest(document_id="d1", filename="a.eml", content_type="message/rfc822")
    with pytest.raises(grpc.RpcError) as error:
        stub.OpenDocument(request, timeout=10)
    assert error.value.code() is grpc.StatusCode.INVALID_ARGUMENT
