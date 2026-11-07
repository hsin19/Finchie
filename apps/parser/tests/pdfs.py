"""Tiny generated PDFs: no real documents in the repository (ADR 0006)."""

import io
from email.message import EmailMessage

import pikepdf

PNG = b"\x89PNG\r\n\x1a\n fake image"


def blank_pdf(user_password: str | None = None) -> bytes:
    pdf = pikepdf.new()
    pdf.add_blank_page()
    buffer = io.BytesIO()
    if user_password is None:
        pdf.save(buffer)
    else:
        pdf.save(buffer, encryption=pikepdf.Encryption(owner="owner-secret", user=user_password, R=6))
    return buffer.getvalue()


def email_with(*attachments: tuple[str, str, bytes]) -> bytes:
    """attachments: (filename, content type, data)."""
    message = EmailMessage()
    message["From"] = "statements@bank.example"
    message["To"] = "someone@example.com"
    message["Subject"] = "Your statement"
    message.set_content("See attachment.")
    for filename, content_type, data in attachments:
        maintype, subtype = content_type.split("/")
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
    return message.as_bytes()


def statement_email(pdf: bytes) -> bytes:
    message = EmailMessage()
    message["From"] = "範例銀行 <statements@bank.example>"
    message["To"] = "someone@example.com"
    message["Subject"] = "範例銀行 2026年11月 信用卡電子帳單"
    message["Date"] = "Fri, 06 Nov 2026 09:30:00 +0800"
    message.set_content("Plain version of the body.")
    message.add_alternative('<p>本期帳單</p><img src="cid:logo@bank.example">', subtype="html")
    html = message.get_body(("html",))
    assert html is not None
    html.add_related(PNG, maintype="image", subtype="png", cid="<logo@bank.example>")
    message.add_attachment(pdf, maintype="application", subtype="octet-stream", filename="帳單_11511.pdf")
    message.add_attachment(b"<html>slip</html>", maintype="text", subtype="html", filename="slip.html")
    message.add_attachment(b"signature", maintype="application", subtype="pkcs7-signature", filename="smime.p7s")
    return message.as_bytes()
