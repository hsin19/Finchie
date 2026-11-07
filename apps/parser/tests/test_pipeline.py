import re
from datetime import date
from decimal import Decimal

import pytest
from pdfs import blank_pdf, email_with, text_pdf

from finchie_parser.errors import InvalidDocumentError, PasswordRequiredError, UnsupportedDocumentError
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

STATEMENT_PDF = text_pdf("FAKE BANK credit card statement")
SLIP_PDF = text_pdf("FAKE BANK payment slip")
CORRUPT_PDF = b"%PDF-1.7 truncated"


class FakeParser(StatementParser):
    name = "fake.statement"
    version = "7"
    institution = "fake"
    filename_pattern = re.compile(r"^FAKE_\d+\.pdf$")
    text_marker = "FAKE BANK"

    def __init__(self) -> None:
        self.parsed: list[str] = []

    def parse(self, document: Document, ocr: Ocr | None) -> Parsed:
        self.parsed.append(document.filename)
        return Parsed(STATEMENT, ["a warning"])


class OtherParser(FakeParser):
    name = "other.statement"
    filename_pattern = re.compile(r"^OTHER_\d+\.pdf$")
    text_marker = "OTHER BANK"


def run(content: bytes, content_type: str = "message/rfc822", passwords: list[str] | None = None):
    parser = FakeParser()
    result = parse_document("doc", content_type, content, passwords=passwords or [], ocr=None, parsers=[parser])
    return result, parser


def test_known_attachment_name_wins_over_other_pdfs() -> None:
    content = email_with(
        ("PaymentSlip.pdf", "application/pdf", SLIP_PDF), ("FAKE_202604.pdf", "application/pdf", STATEMENT_PDF)
    )
    result, parser = run(content)
    assert parser.parsed == ["FAKE_202604.pdf"]
    assert (result.parser, result.parser_version, result.warnings) == ("fake.statement", "7", ["a warning"])


def test_a_pdf_without_the_bank_in_its_text_is_not_parsed_by_its_name() -> None:
    other, fake = OtherParser(), FakeParser()
    content = email_with(("FAKE_202604.pdf", "application/pdf", text_pdf("OTHER BANK statement")))
    result = parse_document("doc", "message/rfc822", content, passwords=[], ocr=None, parsers=[fake, other])
    assert result.parser == "other.statement"
    assert (fake.parsed, other.parsed) == ([], ["FAKE_202604.pdf"])


def test_a_pdf_named_like_a_statement_that_no_parser_recognizes_is_unsupported() -> None:
    with pytest.raises(UnsupportedDocumentError):
        run(email_with(("FAKE_202604.pdf", "application/pdf", blank_pdf())))
    # With the real parsers: a blank PDF named like an HSBC statement used to fail as a layout error.
    with pytest.raises(UnsupportedDocumentError):
        parse_document("eStatement_202604.pdf", "application/pdf", blank_pdf(), passwords=[], ocr=None)


def test_unnamed_statement_is_recognized_by_its_text() -> None:
    content = email_with(("notice.pdf", "application/pdf", blank_pdf()), ("x.pdf", "application/pdf", STATEMENT_PDF))
    _, parser = run(content)
    assert parser.parsed == ["x.pdf"]


@pytest.mark.parametrize("unreadable", [blank_pdf("other"), CORRUPT_PDF], ids=["locked", "corrupt"])
def test_an_unreadable_pdf_does_not_hide_the_statement_after_it(unreadable: bytes) -> None:
    content = email_with(
        ("notice.pdf", "application/pdf", unreadable), ("statement.pdf", "application/pdf", STATEMENT_PDF)
    )
    _, parser = run(content)
    assert parser.parsed == ["statement.pdf"]


def test_encrypted_statement_uses_configured_passwords() -> None:
    content = email_with(("FAKE_1.pdf", "application/pdf", text_pdf("FAKE BANK", user_password="secret")))
    result, _ = run(content, passwords=["nope", "secret"])
    assert result.statement is STATEMENT


def test_encrypted_statement_without_password_needs_one() -> None:
    content = email_with(("FAKE_1.pdf", "application/pdf", text_pdf("FAKE BANK", user_password="secret")))
    with pytest.raises(PasswordRequiredError):
        run(content)


def test_a_locked_statement_by_name_needs_its_password_even_beside_a_slip_that_names_the_bank() -> None:
    content = email_with(
        ("PaymentSlip.pdf", "application/pdf", SLIP_PDF),
        ("FAKE_1.pdf", "application/pdf", text_pdf("FAKE BANK", user_password="secret")),
    )
    with pytest.raises(PasswordRequiredError):
        run(content)


def test_nothing_recognized_reports_a_locked_pdf_before_a_corrupt_one() -> None:
    corrupt = ("broken.pdf", "application/pdf", CORRUPT_PDF)
    locked = ("notice.pdf", "application/pdf", blank_pdf("secret"))
    with pytest.raises(PasswordRequiredError):
        run(email_with(corrupt, locked, ("other.pdf", "application/pdf", blank_pdf())))
    with pytest.raises(InvalidDocumentError):
        run(email_with(corrupt, ("other.pdf", "application/pdf", blank_pdf())))


def test_unrecognized_pdf_is_unsupported() -> None:
    with pytest.raises(UnsupportedDocumentError):
        run(blank_pdf(), content_type="application/pdf")


def test_email_without_pdf_is_unsupported() -> None:
    with pytest.raises(UnsupportedDocumentError):
        run(email_with())
