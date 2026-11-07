import io
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import pikepdf
import pytest
from pdfs import PNG, blank_pdf, email_with, statement_email, text_pdf

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


# HSBC's marker is ASCII, so its statements can be drawn with a standard PDF font.
HSBC_STATEMENT = text_pdf("HSBC Credit Card")
HSBC_SLIP = text_pdf("HSBC payment slip")


def mail(*attachments: tuple[str, bytes]) -> list[File]:
    content = email_with(*((name, "application/pdf", data) for name, data in attachments))
    return open_document("mail.eml", "message/rfc822", content, passwords=[]).files


def test_the_statement_a_parser_knows_by_name_is_primary_even_after_other_pdfs() -> None:
    assert primary(mail(("PaymentSlip.pdf", HSBC_SLIP), ("eStatement_202610.pdf", HSBC_STATEMENT))) == [
        "eStatement_202610.pdf"
    ]


def test_a_pdf_named_like_a_statement_without_its_bank_in_the_text_is_not_primary() -> None:
    assert primary(mail(("other.pdf", HSBC_STATEMENT), ("eStatement_202610.pdf", blank_pdf()))) == ["other.pdf"]


def test_a_statement_recognized_by_its_text_is_primary() -> None:
    assert primary(mail(("notice.pdf", blank_pdf()), ("statement.pdf", HSBC_STATEMENT))) == ["statement.pdf"]


def test_a_locked_pdf_does_not_hide_the_statement_after_it() -> None:
    assert primary(mail(("notice.pdf", blank_pdf("secret")), ("statement.pdf", HSBC_STATEMENT))) == ["statement.pdf"]


def test_a_locked_statement_by_name_is_primary_so_the_viewer_asks_for_its_password() -> None:
    files = mail(("PaymentSlip.pdf", HSBC_SLIP), ("eStatement_202610.pdf", text_pdf("HSBC", user_password="secret")))
    assert [(f.filename, f.locked) for f in files if f.primary] == [("eStatement_202610.pdf", True)]


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


def test_bytes_declared_as_pdf_that_are_not_one_are_neither_called_pdf_nor_primary() -> None:
    content = email_with(
        ("statement.pdf", "application/pdf", b"<html>not a pdf</html>"), ("b.pdf", "application/pdf", blank_pdf())
    )
    files = open_document("mail.eml", "message/rfc822", content, passwords=[]).files
    assert [(f.filename, f.content_type, f.primary) for f in files] == [
        ("statement.pdf", "application/octet-stream", False),
        ("b.pdf", "application/pdf", True),
    ]


def test_a_text_part_with_a_file_name_is_an_attachment_even_marked_inline() -> None:
    message = EmailMessage()
    message["From"] = "statements@bank.example"
    message.set_content("Your statement is attached.")
    message.add_attachment(
        b"<p>statement</p>", maintype="text", subtype="html", filename="statement.html", disposition="inline"
    )
    opened = open_document("mail.eml", "message/rfc822", message.as_bytes(), passwords=[])
    assert opened.email is not None
    assert opened.email.text.strip() == "Your statement is attached."
    assert opened.email.html == ""
    assert [(f.filename, f.content_type, f.data) for f in opened.files] == [
        ("statement.html", "text/html", b"<p>statement</p>")
    ]


def test_only_images_are_inlined_and_a_pdf_the_html_links_by_content_id_stays_a_file() -> None:
    message = EmailMessage()
    message["From"] = "statements@bank.example"
    message.set_content("Plain version of the body.")
    message.add_alternative(
        '<img src="cid:logo@bank.example"><a href="cid:statement@bank.example">statement</a>', subtype="html"
    )
    html = message.get_body(("html",))
    assert html is not None
    html.add_related(PNG, maintype="image", subtype="png", cid="<logo@bank.example>")
    html.add_related(
        blank_pdf(), maintype="application", subtype="pdf", cid="<statement@bank.example>", filename="statement.pdf"
    )

    opened = open_document("mail.eml", "message/rfc822", message.as_bytes(), passwords=[])

    assert opened.email is not None
    assert "data:image/png;base64," in opened.email.html
    assert "data:application/pdf" not in opened.email.html
    assert [(f.filename, f.content_type, f.primary) for f in opened.files] == [
        ("statement.pdf", "application/pdf", True)
    ]
