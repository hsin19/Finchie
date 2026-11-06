import re
from datetime import date
from decimal import Decimal

import pytest
from pdfs import blank_pdf, email_with

from finchie_parser.errors import PasswordRequiredError, UnsupportedDocumentError
from finchie_parser.model import Reconciliation, Statement
from finchie_parser.ocr import Ocr
from finchie_parser.parsers import Parsed, StatementParser
from finchie_parser.pdf import Document
from finchie_parser.pipeline import parse_document

STATEMENT = Statement(
    institution="fake",
    closing_date=date(2026, 4, 7),
    due_date=date(2026, 4, 22),
    currency="TWD",
    total_due=Decimal(0),
    transactions=[],
    reconciliation=Reconciliation(Decimal(0), Decimal(0), "total"),
)


class FakeParser(StatementParser):
    name = "fake.statement"
    version = "7"
    institution = "fake"
    filename_pattern = re.compile(r"^FAKE_\d+\.pdf$")
    text_marker = "never present in a blank page"

    def __init__(self) -> None:
        self.parsed: list[str] = []

    def parse(self, document: Document, ocr: Ocr | None) -> Parsed:
        self.parsed.append(document.filename)
        return Parsed(STATEMENT, ["a warning"])


def run(content: bytes, content_type: str = "message/rfc822", passwords: list[str] | None = None):
    parser = FakeParser()
    result = parse_document("doc", content_type, content, passwords=passwords or [], ocr=None, parsers=[parser])
    return result, parser


def test_known_attachment_name_wins_over_other_pdfs() -> None:
    content = email_with(
        ("PaymentSlip.pdf", "application/pdf", blank_pdf()), ("FAKE_202604.pdf", "application/pdf", blank_pdf())
    )
    result, parser = run(content)
    assert parser.parsed == ["FAKE_202604.pdf"]
    assert (result.parser, result.parser_version, result.warnings) == ("fake.statement", "7", ["a warning"])


def test_encrypted_statement_uses_configured_passwords() -> None:
    content = email_with(("FAKE_1.pdf", "application/pdf", blank_pdf("secret")))
    result, _ = run(content, passwords=["nope", "secret"])
    assert result.statement is STATEMENT


def test_encrypted_statement_without_password_needs_one() -> None:
    content = email_with(("FAKE_1.pdf", "application/pdf", blank_pdf("secret")))
    with pytest.raises(PasswordRequiredError):
        run(content)


def test_unrecognized_pdf_is_unsupported() -> None:
    with pytest.raises(UnsupportedDocumentError):
        run(blank_pdf(), content_type="application/pdf")


def test_email_without_pdf_is_unsupported() -> None:
    with pytest.raises(UnsupportedDocumentError):
        run(email_with())
