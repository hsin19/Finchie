import pytest
from pdfs import blank_pdf

from finchie_parser.documents import Attachment
from finchie_parser.errors import InvalidDocumentError, PasswordRequiredError
from finchie_parser.pdf import open_pdf


def test_unencrypted_pdf_opens_without_passwords() -> None:
    with open_pdf(Attachment("a.pdf", blank_pdf()), []) as document:
        assert document.page_texts() == [""]


def test_encrypted_pdf_opens_with_any_configured_password() -> None:
    with open_pdf(Attachment("a.pdf", blank_pdf("right")), ["wrong", "right"]) as document:
        assert len(document.page_texts()) == 1


def test_encrypted_pdf_without_a_matching_password_is_rejected() -> None:
    with pytest.raises(PasswordRequiredError):
        open_pdf(Attachment("a.pdf", blank_pdf("right")), ["wrong"])


def test_corrupt_pdf_is_invalid() -> None:
    with pytest.raises(InvalidDocumentError):
        open_pdf(Attachment("a.pdf", b"%PDF-1.7 truncated"), [])
