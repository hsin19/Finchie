import io
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import pikepdf
import pytest
from pdfs import PNG, blank_pdf, email_with, statement_email

from finchie_parser.errors import InvalidDocumentError, UnsupportedDocumentError
from finchie_parser.reading import File, open_document


def opens_without_password(data: bytes) -> bool:
    try:
        pikepdf.open(io.BytesIO(data)).close()
    except pikepdf.PasswordError:
        return False
    return True


def test_email_shows_headers_html_body_with_inline_images_and_its_attachments() -> None:
    opened = open_document("mail.eml", "message/rfc822", statement_email(blank_pdf("secret")), passwords=["secret"])

    mail = opened.email
    assert mail is not None
    assert mail.sender == "範例銀行 <statements@bank.example>"
    assert mail.recipient == "someone@example.com"
    assert mail.subject == "範例銀行 2026年11月 信用卡電子帳單"
    assert mail.date == datetime(2026, 11, 6, 9, 30, tzinfo=timezone(timedelta(hours=8)))
    assert "本期帳單" in mail.html
    assert "cid:" not in mail.html
    assert "data:image/png;base64," in mail.html
    assert mail.text == ""

    assert [(f.filename, f.content_type, f.locked) for f in opened.files] == [
        ("帳單_11511.pdf", "application/pdf", False),
        ("slip.html", "text/html", False),
    ]
    assert opens_without_password(opened.files[0].data)
    assert opened.files[1].data == b"<html>slip</html>"


def test_pdf_no_configured_password_opens_comes_back_locked_as_received() -> None:
    pdf = blank_pdf("secret")
    opened = open_document("mail.eml", "message/rfc822", statement_email(pdf), passwords=["wrong"])
    assert opened.files[0].locked
    assert opened.files[0].data == pdf


def test_plain_text_email_has_a_text_body() -> None:
    message = EmailMessage()
    message["From"] = "statements@bank.example"
    message["Subject"] = "Statement"
    message.set_content("Your statement is attached.")
    opened = open_document("mail.eml", "message/rfc822", message.as_bytes(), passwords=[])
    assert opened.email is not None
    assert opened.email.text.strip() == "Your statement is attached."
    assert opened.email.html == ""
    assert opened.email.date is None
    assert opened.files == []


def test_bare_pdf_is_its_one_file_decrypted() -> None:
    opened = open_document("statement.pdf", "application/pdf", blank_pdf("secret"), passwords=["secret"])
    assert opened.email is None
    assert [(f.filename, f.content_type, f.locked) for f in opened.files] == [
        ("statement.pdf", "application/pdf", False)
    ]
    assert opens_without_password(opened.files[0].data)


def test_corrupt_pdf_is_shown_as_it_arrived() -> None:
    opened = open_document("broken.pdf", "application/pdf", b"%PDF-1.7 truncated", passwords=[])
    assert opened.files[0].data == b"%PDF-1.7 truncated"
    assert not opened.files[0].locked


def test_empty_document_is_invalid() -> None:
    with pytest.raises(InvalidDocumentError):
        open_document("a.eml", "message/rfc822", b"", passwords=[])


def test_other_files_are_unsupported() -> None:
    with pytest.raises(UnsupportedDocumentError):
        open_document("a.png", "image/png", PNG, passwords=[])


def primary(files: list[File]) -> list[str]:
    return [f.filename for f in files if f.primary]


def test_the_statement_a_parser_knows_by_name_is_primary_even_after_other_pdfs() -> None:
    pdf = blank_pdf()
    content = email_with(
        ("TSB_PaymentSlip_202610.pdf", "application/pdf", pdf),
        ("TSB_Creditcard_Estatement_202610.pdf", "application/octet-stream", pdf),
    )
    opened = open_document("mail.eml", "message/rfc822", content, passwords=[])
    assert primary(opened.files) == ["TSB_Creditcard_Estatement_202610.pdf"]


def test_without_a_known_name_the_first_pdf_is_primary() -> None:
    pdf = blank_pdf()
    content = email_with(
        ("notice.html", "text/html", b"<p>hi</p>"), ("a.pdf", "application/pdf", pdf), ("b.pdf", "application/pdf", pdf)
    )
    assert primary(open_document("mail.eml", "message/rfc822", content, passwords=[]).files) == ["a.pdf"]
    assert primary(open_document("x.pdf", "application/pdf", pdf, passwords=[]).files) == ["x.pdf"]


def test_an_email_without_pdfs_has_no_primary() -> None:
    content = email_with(("notice.html", "text/html", b"<p>hi</p>"))
    assert primary(open_document("mail.eml", "message/rfc822", content, passwords=[]).files) == []
