import pytest
from pdfs import blank_pdf, email_with

from finchie_parser.documents import extract_pdfs
from finchie_parser.errors import InvalidDocumentError, UnsupportedDocumentError


def test_bare_pdf_is_its_own_attachment() -> None:
    data = blank_pdf()
    assert [(a.filename, a.data) for a in extract_pdfs("x.pdf", "application/pdf", data)] == [("x.pdf", data)]


def test_email_yields_pdf_attachments_including_octet_stream_and_encoded_names() -> None:
    pdf = blank_pdf()
    content = email_with(
        ("信用卡電子帳單消費明細_11510.pdf", "application/octet-stream", pdf),
        ("eBarCodeFullPay.html", "text/html", b"<html></html>"),
        ("slip.pdf", "application/pdf", pdf),
    )
    names = [a.filename for a in extract_pdfs("statement.eml", "message/rfc822", content)]
    assert names == ["信用卡電子帳單消費明細_11510.pdf", "slip.pdf"]


def test_email_without_pdfs_yields_nothing() -> None:
    assert extract_pdfs("a.eml", "message/rfc822", email_with()) == []


def test_empty_document_is_invalid() -> None:
    with pytest.raises(InvalidDocumentError):
        extract_pdfs("a.pdf", "application/pdf", b"")


def test_pdf_content_type_with_other_bytes_is_invalid() -> None:
    with pytest.raises(InvalidDocumentError):
        extract_pdfs("a.pdf", "application/pdf", b"not a pdf")


def test_unknown_content_type_is_unsupported() -> None:
    with pytest.raises(UnsupportedDocumentError):
        extract_pdfs("a.png", "image/png", b"\x89PNG")
